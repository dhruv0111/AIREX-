"""Experiment execution runner (Phase 6).

Drives experiment run lifecycle: queues, executes baseline & candidate evaluation runs,
polls for completion, aggregates metrics, performs statistical comparisons,
runs regression analysis, evaluates quality gates, and persists results.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.metrics import (
    airex_experiments_total,
    airex_experiment_runs_total,
    airex_experiment_failures_total,
    airex_experiment_duration_seconds,
    airex_experiment_regressions_total,
    airex_quality_gate_failures_total,
)
from app.evaluations.gates import compute_overall_gate_status, evaluate_gate
from app.evaluations.regression import analyze_regression
from app.evaluations.statistics import calculate_comparison_statistics, calculate_mean
from app.models import EvaluationResult, EvaluationRun, PromptVersion
from app.repositories.audit import AuditRepository
from app.repositories.evaluation import EvaluationResultRepository
from app.repositories.experiment import ExperimentRepository
from app.schemas.evaluation import EvaluationConfiguration, EvaluationCreate, EvaluationExecutionConfig, EvaluatorConfig
from app.services.evaluation import EvaluationService

logger = logging.getLogger("airex.experiments")


class ExperimentRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._settings = get_settings()

    async def run(self, run_id: UUID) -> dict[str, Any]:
        """Execute an experiment run."""
        if isinstance(run_id, str):
            run_id = UUID(run_id)
        start = time.perf_counter()

        async with self._session_factory() as session:
            repo = ExperimentRepository(session)
            run = await repo.get_run_by_id(run_id)
            if run is None:
                return {"status": "NOT_FOUND"}

            if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                return {"status": run.status, "idempotent": True}

            exp = await repo.get_by_id(run.experiment_id)
            if exp is None:
                return {"status": "NOT_FOUND"}

            # Transition to RUNNING
            await repo.set_run_status(run, "RUNNING")
            await repo.set_status(exp, "RUNNING")
            await repo.touch_run_heartbeat(run)
            await repo.touch_heartbeat(exp)

            await AuditRepository(session).record(
                action="EXPERIMENT_STARTED",
                organization_id=None,
                user_id=run.created_by,
                resource_type="experiment_run",
                resource_id=run.id,
            )
            airex_experiment_runs_total.labels(status="RUNNING").inc()
            await session.commit()

        try:
            return await self._execute(run_id, start)
        except Exception as exc:
            logger.exception("experiment run failed", extra={"run_id": str(run_id)})
            async with self._session_factory() as session:
                repo = ExperimentRepository(session)
                run = await repo.get_run_by_id(run_id)
                exp = await repo.get_by_id(run.experiment_id)
                await repo.set_run_status(run, "FAILED")
                await repo.set_status(exp, "FAILED")
                await repo.set_run_error(run, str(exc)[:2000])

                # Update associated CI run
                from sqlalchemy import select
                from app.models.ci import CIRun
                stmt_ci = select(CIRun).where(CIRun.experiment_run_id == run.id)
                res_ci = await session.execute(stmt_ci)
                ci_run = res_ci.scalar_one_or_none()
                if ci_run:
                    ci_run.status = "FAILED"
                    ci_run.outcome = "FAIL"
                    ci_run.completed_at = datetime.now(UTC)
                    if ci_run.created_at:
                        ci_run.duration_seconds = (ci_run.completed_at - ci_run.created_at).total_seconds()
                    
                    await AuditRepository(session).record(
                        action="CI_RUN_FAILED",
                        organization_id=None,
                        user_id=run.created_by,
                        resource_type="ci_run",
                        resource_id=ci_run.id,
                        metadata={"reason": str(exc)[:500], "ci_run_id": ci_run.ci_run_id},
                    )
                    from app.core.metrics import ci_runs_total, ci_run_failures_total
                    ci_runs_total.labels(provider=ci_run.ci_provider, status="FAILED").inc()
                    ci_run_failures_total.labels(category="execution_failure").inc()

                await AuditRepository(session).record(
                    action="EXPERIMENT_FAILED",
                    organization_id=None,
                    user_id=run.created_by,
                    resource_type="experiment_run",
                    resource_id=run.id,
                    metadata={"reason": str(exc)[:1000]},
                )
                airex_experiment_failures_total.inc()
                airex_experiment_runs_total.labels(status="FAILED").inc()
                await session.commit()
            return {"status": "FAILED"}

    async def _execute(self, run_id: UUID, start: float) -> dict[str, Any]:
        async with self._session_factory() as session:
            repo = ExperimentRepository(session)
            run = await repo.get_run_by_id(run_id)
            exp = await repo.get_by_id(run.experiment_id)
            variants = await repo.get_variants_for_experiment(exp.id)
            gates = await repo.get_quality_gates_for_experiment(exp.id)

            baseline_var = next((v for v in variants if v.variant_type == "BASELINE"), None)
            candidate_var = next((v for v in variants if v.variant_type == "CANDIDATE"), None)

            if not baseline_var or not candidate_var:
                raise ValueError("Experiment variants configuration is incomplete.")

            # Load project to find org_id
            from app.models.project import Project
            project = await session.get(Project, exp.project_id)
            org_id = project.organization_id if project else None
            if not org_id:
                raise ValueError("Project organization not resolved.")

            eval_service = EvaluationService(session)

            # Resolve baseline configuration
            baseline_evaluators = (baseline_var.configuration or {}).get("evaluators") or (exp.configuration or {}).get("evaluators") or [{"type": "exact_match", "enabled": True}]
            baseline_prompt_content = None
            if baseline_var.prompt_version_id:
                pv = await session.get(PromptVersion, baseline_var.prompt_version_id)
                if pv:
                    baseline_prompt_content = pv.content

            base_eval_config = EvaluationConfiguration(
                evaluators=[EvaluatorConfig(**ev) for ev in baseline_evaluators],
                execution=EvaluationExecutionConfig(
                    max_concurrency=int((baseline_var.configuration or {}).get("max_concurrency", 5)),
                    timeout_seconds=int((baseline_var.configuration or {}).get("timeout_seconds", 30)),
                    pass_policy=(baseline_var.configuration or {}).get("pass_policy", "ALL"),
                    threshold=(baseline_var.configuration or {}).get("threshold"),
                ),
                prompt_version_content=baseline_prompt_content,
            )

            # Create baseline evaluation run (this automatically queues it)
            baseline_payload = EvaluationCreate(
                project_id=exp.project_id,
                environment_id=None,
                dataset_version_id=baseline_var.dataset_version_id or exp.dataset_version_id,
                model_id=baseline_var.model_id or exp.model_id,
                configuration=base_eval_config,
            )
            base_run_resp = await eval_service.create(
                organization_id=org_id,
                user_id=run.created_by,
                payload=baseline_payload,
            )

            # Resolve candidate configuration
            candidate_evaluators = (candidate_var.configuration or {}).get("evaluators") or (exp.configuration or {}).get("evaluators") or [{"type": "exact_match", "enabled": True}]
            candidate_prompt_content = None
            if candidate_var.prompt_version_id:
                pv = await session.get(PromptVersion, candidate_var.prompt_version_id)
                if pv:
                    candidate_prompt_content = pv.content

            cand_eval_config = EvaluationConfiguration(
                evaluators=[EvaluatorConfig(**ev) for ev in candidate_evaluators],
                execution=EvaluationExecutionConfig(
                    max_concurrency=int((candidate_var.configuration or {}).get("max_concurrency", 5)),
                    timeout_seconds=int((candidate_var.configuration or {}).get("timeout_seconds", 30)),
                    pass_policy=(candidate_var.configuration or {}).get("pass_policy", "ALL"),
                    threshold=(candidate_var.configuration or {}).get("threshold"),
                ),
                prompt_version_content=candidate_prompt_content,
            )

            # Create candidate evaluation run
            candidate_payload = EvaluationCreate(
                project_id=exp.project_id,
                environment_id=None,
                dataset_version_id=candidate_var.dataset_version_id or exp.dataset_version_id,
                model_id=candidate_var.model_id or exp.model_id,
                configuration=cand_eval_config,
            )
            cand_run_resp = await eval_service.create(
                organization_id=org_id,
                user_id=run.created_by,
                payload=candidate_payload,
            )

            # Associate run IDs on ExperimentRun
            run.baseline_run_id = base_run_resp.id
            run.candidate_run_id = cand_run_resp.id
            await session.commit()

            # In test/in-memory environment, execute evaluations synchronously
            if self._settings.app_env == "test" or self._settings.redis_url.startswith("memory://"):
                from app.evaluations.runner import EvaluationRunner
                eval_runner = EvaluationRunner(self._session_factory)
                await eval_runner.run(base_run_resp.id)
                await eval_runner.run(cand_run_resp.id)

        # Polling loop waiting for both evaluation runs to complete
        logger.info(f"Experiment run {run_id} enqueued baseline evaluation {base_run_resp.id} and candidate {cand_run_resp.id}. Polling for completion.")
        while True:
            async with self._session_factory() as session:
                repo = ExperimentRepository(session)
                run = await repo.get_run_by_id(run_id)
                exp = await repo.get_by_id(run.experiment_id)

                # Check if experiment run itself was cancelled externally
                if run.status == "CANCELLED":
                    logger.info(f"Experiment run {run_id} cancelled.")
                    return {"status": "CANCELLED"}

                base_run = await session.get(EvaluationRun, run.baseline_run_id)
                cand_run = await session.get(EvaluationRun, run.candidate_run_id)

                if base_run.status in ("COMPLETED", "FAILED", "CANCELLED") and cand_run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                    break

                # Send heartbeat
                await repo.touch_run_heartbeat(run)
                await repo.touch_heartbeat(exp)
                await session.commit()

            await asyncio.sleep(2)

        # Retrieve final statuses
        async with self._session_factory() as session:
            base_run = await session.get(EvaluationRun, run.baseline_run_id)
            cand_run = await session.get(EvaluationRun, run.candidate_run_id)

            if base_run.status != "COMPLETED" or cand_run.status != "COMPLETED":
                raise RuntimeError(
                    f"Underlying evaluations did not complete successfully. "
                    f"Baseline: {base_run.status}, Candidate: {cand_run.status}"
                )

            # Extract evaluation results for comparison
            results_repo = EvaluationResultRepository(session)
            base_results = await results_repo.all_for_run(base_run.id)
            cand_results = await results_repo.all_for_run(cand_run.id)

        # Aggregate metric observations
        # Format metric keys as: e.g. "accuracy", "latency_ms", "estimated_cost", "combined_score", "judge_score"
        baseline_metrics: dict[str, list[float]] = {
            "accuracy": [1.0 if r.status == "PASS" else 0.0 for r in base_results],
            "latency_ms": [float(r.latency_ms) for r in base_results if r.latency_ms is not None],
            "estimated_cost": [float(r.estimated_cost) for r in base_results if r.estimated_cost is not None],
            "combined_score": [float(r.combined_score) for r in base_results if r.combined_score is not None],
            "judge_score": [float(r.judge_score) for r in base_results if r.judge_score is not None],
        }

        candidate_metrics: dict[str, list[float]] = {
            "accuracy": [1.0 if r.status == "PASS" else 0.0 for r in cand_results],
            "latency_ms": [float(r.latency_ms) for r in cand_results if r.latency_ms is not None],
            "estimated_cost": [float(r.estimated_cost) for r in cand_results if r.estimated_cost is not None],
            "combined_score": [float(r.combined_score) for r in cand_results if r.combined_score is not None],
            "judge_score": [float(r.judge_score) for r in cand_results if r.judge_score is not None],
        }

        # Also extract individual evaluator scores
        for results, metrics_dict in [(base_results, baseline_metrics), (cand_results, candidate_metrics)]:
            for r in results:
                if r.score:
                    for ev in r.score:
                        name = ev.get("evaluator")
                        val = ev.get("score")
                        if name and val is not None:
                            key = f"evaluator_{name}"
                            if key not in metrics_dict:
                                metrics_dict[key] = []
                            metrics_dict[key].append(float(val))

        # Perform comparisons and statistics
        comparisons = []
        regressions = []

        async with self._session_factory() as session:
            repo = ExperimentRepository(session)
            run = await repo.get_run_by_id(run_id)
            exp = await repo.get_by_id(run.experiment_id)

            comparison_map = {}

            # Iterate over all metrics that have candidate or baseline observations
            for metric in set(list(baseline_metrics.keys()) + list(candidate_metrics.keys())):
                base_obs = baseline_metrics.get(metric, [])
                cand_obs = candidate_metrics.get(metric, [])

                if not base_obs or not cand_obs:
                    continue

                m1 = calculate_mean(base_obs)
                m2 = calculate_mean(cand_obs)

                # Statistical t-test analysis
                stats = calculate_comparison_statistics(base_obs, cand_obs)
                p_value = stats.get("p_value") if stats else None

                # Regression analysis
                analysis = analyze_regression(metric, m1, m2, p_value)

                # Save comparison record
                comp = await repo.create_comparison(
                    run_id=run.id,
                    metric_name=metric,
                    baseline_value=m1,
                    candidate_value=m2,
                    absolute_difference=analysis["absolute_difference"],
                    relative_difference=analysis["relative_difference"],
                    classification=analysis["classification"],
                    statistical_metadata=stats,
                )
                comparison_map[metric] = comp

                # Save regression record if severity is not NONE
                if analysis["severity"] != "NONE":
                    reg = await repo.create_regression(
                        comparison_id=comp.id,
                        metric_name=metric,
                        severity=analysis["severity"],
                        baseline_value=m1,
                        candidate_value=m2,
                        threshold=0.02,  # logic default
                        explanation=f"Metric '{metric}' regressed with severity {analysis['severity']}.",
                    )
                    regressions.append(reg)
                    airex_experiment_regressions_total.inc()
                    await AuditRepository(session).record(
                        action="REGRESSION_DETECTED",
                        organization_id=org_id,
                        user_id=run.created_by,
                        resource_type="regression",
                        resource_id=reg.id,
                        metadata={
                            "metric": metric,
                            "baseline": m1,
                            "candidate": m2,
                            "severity": analysis["severity"],
                        },
                    )

            # Evaluate quality gates
            gate_results_payload = []
            for gate in gates:
                comp = comparison_map.get(gate.metric_name)
                comp_dict = {
                    "candidate_value": comp.candidate_value if comp else None,
                    "absolute_difference": comp.absolute_difference if comp else None,
                    "relative_difference": comp.relative_difference if comp else None,
                } if comp else None

                status, actual_val = evaluate_gate(gate.gate_type, gate.operator, gate.threshold, comp_dict)

                from app.core.metrics import quality_gate_enforcements_total, quality_gate_blocks_total
                quality_gate_enforcements_total.labels(metric_name=gate.metric_name).inc()
                if status == "FAIL":
                    quality_gate_blocks_total.labels(metric_name=gate.metric_name).inc()

                gate_res = await repo.create_gate_result(
                    run_id=run.id,
                    quality_gate_id=gate.id,
                    metric_name=gate.metric_name,
                    actual_value=actual_val,
                    status=status,
                )
                gate_results_payload.append({
                    "is_required": gate.is_required,
                    "status": status,
                })

                if status == "FAIL":
                    airex_quality_gate_failures_total.inc()
                    await AuditRepository(session).record(
                        action="QUALITY_GATE_FAILED",
                        organization_id=org_id,
                        user_id=run.created_by,
                        resource_type="quality_gate_result",
                        resource_id=gate_res.id,
                        metadata={
                            "metric": gate.metric_name,
                            "threshold": gate.threshold,
                            "operator": gate.operator,
                            "actual": actual_val,
                        },
                    )

            # Compute overall gate result (PASS, FAIL, INCONCLUSIVE)
            overall_gate_status = compute_overall_gate_status(gate_results_payload)

            # Transition experiment and run status
            await repo.set_run_status(run, "COMPLETED")
            exp_status = "COMPLETED"
            if overall_gate_status == "FAIL":
                exp_status = "FAILED"
            elif overall_gate_status == "INCONCLUSIVE":
                exp_status = "INCONCLUSIVE"
            await repo.set_status(exp, exp_status)
            
            # Touch completion timestamp
            run.completed_at = datetime.now(UTC)
            exp.completed_at = datetime.now(UTC)

            # Update associated CI run
            from sqlalchemy import select
            from app.models.ci import CIRun
            stmt_ci = select(CIRun).where(CIRun.experiment_run_id == run.id)
            res_ci = await session.execute(stmt_ci)
            ci_run = res_ci.scalar_one_or_none()
            if ci_run:
                ci_outcome = "PASS" if overall_gate_status in ("PASS", "INCONCLUSIVE") else "FAIL"
                ci_run.status = "COMPLETED"
                ci_run.outcome = ci_outcome
                ci_run.completed_at = datetime.now(UTC)
                if ci_run.created_at:
                    ci_run.duration_seconds = (ci_run.completed_at - ci_run.created_at).total_seconds()
                
                await AuditRepository(session).record(
                    action="CI_RUN_COMPLETED",
                    organization_id=org_id,
                    user_id=run.created_by,
                    resource_type="ci_run",
                    resource_id=ci_run.id,
                    metadata={"outcome": ci_outcome, "ci_run_id": ci_run.ci_run_id},
                )
                from app.core.metrics import ci_runs_total, ci_run_duration_seconds
                ci_runs_total.labels(provider=ci_run.ci_provider, status="COMPLETED").inc()
                ci_run_duration_seconds.observe(ci_run.duration_seconds or 0.0)

            await AuditRepository(session).record(
                action="EXPERIMENT_COMPLETED",
                organization_id=org_id,
                user_id=run.created_by,
                resource_type="experiment_run",
                resource_id=run.id,
                metadata={
                    "overall_quality_gate": overall_gate_status,
                    "regressions_count": len(regressions),
                },
            )
            airex_experiment_runs_total.labels(status="COMPLETED").inc()
            airex_experiments_total.inc()

            # Automatically publish canonical compliance evidence (Phase 15)
            if org_id is not None:
                from app.services.evidence_service import publish_canonical_evidence
                await publish_canonical_evidence(
                    session=session,
                    organization_id=org_id,
                    source_type="experiment_run",
                    source_id=str(run.id),
                    project_id=project.id if project else None,
                    metadata_summary={
                        "overall_quality_gate": overall_gate_status,
                        "regressions_count": len(regressions),
                    },
                )

            await session.commit()

        duration = time.perf_counter() - start
        airex_experiment_duration_seconds.observe(duration)

        return {
            "status": "COMPLETED",
            "overall_quality_gate": overall_gate_status,
            "regressions_count": len(regressions),
        }


async def recover_stale_experiments(session_factory) -> int:
    """Recover running experiment runs with stale heartbeats."""
    settings = get_settings()
    threshold = datetime.now(UTC) - timedelta(seconds=settings.evaluation_stale_timeout_seconds)
    recovered = 0

    async with session_factory() as session:
        repo = ExperimentRepository(session)
        stale = await repo.get_stale_runs(threshold)
        for run in stale:
            exp = await repo.get_by_id(run.experiment_id)
            await repo.set_run_status(run, "FAILED")
            if exp:
                await repo.set_status(exp, "FAILED")

            await AuditRepository(session).record(
                action="EXPERIMENT_FAILED",
                organization_id=None,
                user_id=run.created_by,
                resource_type="experiment_run",
                resource_id=run.id,
                metadata={"reason": "stale experiment recovered after worker crash"},
            )
            airex_experiment_runs_total.labels(status="FAILED").inc()
            recovered += 1

        if stale:
            await session.commit()
    return recovered
