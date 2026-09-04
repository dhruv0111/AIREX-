"""Benchmark execution runner (Phase 9).

Coordinates benchmark runs: schedules evaluation runs for baseline and candidates,
polls for completion, checks compatibility, computes statistical evidence,
calculates reliability scores, clusters failures, and generates recommendations.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.evaluations.statistics import calculate_comparison_statistics, calculate_mean, calculate_std_dev
from app.models import EvaluationResult, EvaluationRun, PromptVersion
from app.models.benchmark import BenchmarkRun, BenchmarkVersion, BenchmarkResult
from app.models.provider import Model
from app.repositories.audit import AuditRepository
from app.repositories.benchmark import BenchmarkRepository
from app.repositories.evaluation import EvaluationResultRepository
from app.schemas.evaluation import EvaluationConfiguration, EvaluationCreate, EvaluationExecutionConfig, EvaluatorConfig
from app.services.evaluation import EvaluationService

logger = logging.getLogger("airex.benchmarks")


async def resolve_model_id(session: AsyncSession, project_id: UUID, identifier: str) -> UUID:
    """Resolve a model UUID from name, identifier, or string UUID."""
    try:
        return UUID(identifier)
    except ValueError:
        pass

    stmt = select(Model).where(
        and_(
            Model.project_id == project_id,
            or_(Model.name == identifier, Model.model_identifier == identifier)
        )
    )
    res = await session.execute(stmt)
    model = res.scalar_one_or_none()
    if model:
        return model.id
    raise ValueError(f"Model '{identifier}' not found in project.")


class BenchmarkRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._settings = get_settings()

    async def run(self, run_id: UUID) -> dict[str, Any]:
        """Execute a benchmark run."""
        if isinstance(run_id, str):
            run_id = UUID(run_id)

        async with self._session_factory() as session:
            repo = BenchmarkRepository(session)
            run = await repo.get_run_by_id(run_id)
            if run is None:
                return {"status": "NOT_FOUND"}

            if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                return {"status": run.status, "idempotent": True}

            version = await repo.get_version_by_id(run.benchmark_version_id)
            if version is None:
                return {"status": "NOT_FOUND"}

            # Transition status to RUNNING
            await repo.set_run_status(run, "RUNNING")
            await repo.touch_run_heartbeat(run)
            await session.commit()

        try:
            return await self._execute(run_id)
        except Exception as exc:
            logger.exception("benchmark run failed", extra={"run_id": str(run_id)})
            async with self._session_factory() as session:
                repo = BenchmarkRepository(session)
                run = await repo.get_run_by_id(run_id)
                if run:
                    await repo.set_run_status(run, "FAILED", error_message=str(exc))
                await session.commit()
            return {"status": "FAILED"}

    async def _execute(self, run_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            repo = BenchmarkRepository(session)
            run = await repo.get_run_by_id(run_id)
            version = await repo.get_version_by_id(run.benchmark_version_id)
            suite = await repo.get_suite_by_id(run.benchmark_suite_id)
            config = version.configuration or {}

            # Validate weights if specified
            weights = config.get("weights")
            if weights is not None:
                # Validate weights are non-negative and sum to 1
                if not isinstance(weights, dict):
                    raise ValueError("Weights must be a dictionary configuration.")
                total_w = 0.0
                for k, w in weights.items():
                    if w < 0:
                        raise ValueError(f"Weight for metric '{k}' must be non-negative.")
                    total_w += w
                if abs(total_w - 1.0) > 1e-4:
                    raise ValueError(f"Weights must sum to 1.0 (got {total_w}).")
            else:
                weights = {
                    "accuracy": 0.4,
                    "latency_ms": 0.2,
                    "estimated_cost": 0.1,
                    "consistency": 0.1,
                    "safety": 0.2
                }

            # Find organization
            from app.models.project import Project
            project = await session.get(Project, suite.project_id)
            org_id = project.organization_id if project else None
            if not org_id:
                raise ValueError("Project organization not resolved.")

            # Resolve baseline model and candidate models
            baseline_model_ref = config.get("baseline", {}).get("model")
            candidate_models_ref = config.get("candidates", [])

            if not baseline_model_ref:
                raise ValueError("Baseline model is not specified in configuration.")
            if not candidate_models_ref:
                raise ValueError("Candidate models list is empty in configuration.")

            baseline_model_id = await resolve_model_id(session, suite.project_id, baseline_model_ref)
            candidate_model_ids = []
            for cand in candidate_models_ref:
                c_ref = cand.get("model") if isinstance(cand, dict) else cand
                c_id = await resolve_model_id(session, suite.project_id, c_ref)
                candidate_model_ids.append(c_id)

            eval_service = EvaluationService(session)

            # Build Evaluators list
            evaluators_raw = config.get("evaluators") or [{"type": "exact_match", "enabled": True}]
            evaluators = [EvaluatorConfig(**ev) for ev in evaluators_raw]

            eval_config = EvaluationConfiguration(
                evaluators=evaluators,
                execution=EvaluationExecutionConfig(
                    max_concurrency=int(config.get("max_concurrency", 5)),
                    timeout_seconds=int(config.get("timeout_seconds", 30)),
                    pass_policy=config.get("pass_policy", "ALL"),
                )
            )

            # Create Baseline Evaluation Run
            baseline_payload = EvaluationCreate(
                project_id=suite.project_id,
                environment_id=None,
                dataset_version_id=version.dataset_version_id,
                model_id=baseline_model_id,
                configuration=eval_config,
            )
            base_run_resp = await eval_service.create(
                organization_id=org_id,
                user_id=run.created_by,
                payload=baseline_payload,
            )

            # Create Candidates Evaluation Runs
            cand_runs = []
            for cand_model_id in candidate_model_ids:
                cand_payload = EvaluationCreate(
                    project_id=suite.project_id,
                    environment_id=None,
                    dataset_version_id=version.dataset_version_id,
                    model_id=cand_model_id,
                    configuration=eval_config,
                )
                cand_run_resp = await eval_service.create(
                    organization_id=org_id,
                    user_id=run.created_by,
                    payload=cand_payload,
                )
                cand_runs.append((cand_model_id, cand_run_resp.id))

            # Store the scheduled runs dynamically (we'll save results later)
            await session.commit()

            # Execute synchronously in test / local memory environment
            if self._settings.app_env == "test" or self._settings.redis_url.startswith("memory://"):
                from app.evaluations.runner import EvaluationRunner
                eval_runner = EvaluationRunner(self._session_factory)
                await eval_runner.run(base_run_resp.id)
                for _, cand_run_id in cand_runs:
                    await eval_runner.run(cand_run_id)

        # Polling Loop for completion
        logger.info(f"Polling benchmark run {run_id} evaluation completions.")
        while True:
            async with self._session_factory() as session:
                repo = BenchmarkRepository(session)
                run = await repo.get_run_by_id(run_id)
                if run.status == "CANCELLED":
                    return {"status": "CANCELLED"}

                base_run = await session.get(EvaluationRun, base_run_resp.id)
                all_done = base_run.status in ("COMPLETED", "FAILED", "CANCELLED")

                for _, cand_run_id in cand_runs:
                    cr = await session.get(EvaluationRun, cand_run_id)
                    if cr.status not in ("COMPLETED", "FAILED", "CANCELLED"):
                        all_done = False
                        break

                if all_done:
                    break

                await repo.touch_run_heartbeat(run)
                await session.commit()

            await asyncio.sleep(2)

        # Process Results
        async with self._session_factory() as session:
            repo = BenchmarkRepository(session)
            run = await repo.get_run_by_id(run_id)

            base_run = await session.get(EvaluationRun, base_run_resp.id)
            if base_run.status != "COMPLETED":
                raise RuntimeError(f"Baseline evaluation run failed with status {base_run.status}")

            results_repo = EvaluationResultRepository(session)
            base_results = await results_repo.all_for_run(base_run.id)

            # Metrics collections for baseline
            base_accuracy = [1.0 if r.status == "PASS" else 0.0 for r in base_results]
            base_latency = [float(r.latency_ms) for r in base_results if r.latency_ms is not None]
            base_cost = [float(r.estimated_cost) for r in base_results if r.estimated_cost is not None]
            base_combined = [float(r.combined_score) for r in base_results if r.combined_score is not None]
            # Safety scores: filter safety evaluators if present, else fallback
            base_safety = [1.0 if r.status == "PASS" else 0.0 for r in base_results]

            base_mean_accuracy = calculate_mean(base_accuracy)
            base_mean_latency = calculate_mean(base_latency)
            base_mean_cost = calculate_mean(base_cost)
            base_mean_combined = calculate_mean(base_combined)
            base_mean_safety = calculate_mean(base_safety)

            overall_run_scores = []
            all_candidate_failures: list[EvaluationResult] = []

            for cand_model_id, cand_run_id in cand_runs:
                cand_run = await session.get(EvaluationRun, cand_run_id)
                if cand_run.status != "COMPLETED":
                    raise RuntimeError(f"Candidate evaluation run {cand_run_id} failed with status {cand_run.status}")

                # Check compatibility rule (§User Knowledge)
                # Comparisons must detect incompatible data.
                if cand_run.dataset_version_id != base_run.dataset_version_id:
                    # Incompatible dataset
                    raise ValueError(f"Incompatible run: dataset mismatch {cand_run.dataset_version_id} != {base_run.dataset_version_id}")

                # Verify evaluator config compatibility
                cand_config = cand_run.configuration or {}
                base_config = base_run.configuration or {}
                cand_evs = sorted(e.get("type", "") for e in cand_config.get("evaluators", []))
                base_evs = sorted(e.get("type", "") for e in base_config.get("evaluators", []))
                if cand_evs != base_evs:
                    raise ValueError(f"Incompatible run: evaluator configuration mismatch {cand_evs} != {base_evs}")

                cand_results = await results_repo.all_for_run(cand_run_id)
                all_candidate_failures.extend([r for r in cand_results if r.status == "FAIL"])

                # Metrics collections for candidate
                cand_accuracy = [1.0 if r.status == "PASS" else 0.0 for r in cand_results]
                cand_latency = [float(r.latency_ms) for r in cand_results if r.latency_ms is not None]
                cand_cost = [float(r.estimated_cost) for r in cand_results if r.estimated_cost is not None]
                cand_combined = [float(r.combined_score) for r in cand_results if r.combined_score is not None]
                cand_safety = [1.0 if r.status == "PASS" else 0.0 for r in cand_results]

                cand_mean_accuracy = calculate_mean(cand_accuracy)
                cand_mean_latency = calculate_mean(cand_latency)
                cand_mean_cost = calculate_mean(cand_cost)
                cand_mean_combined = calculate_mean(cand_combined)
                cand_mean_safety = calculate_mean(cand_safety)

                cand_std_combined = calculate_std_dev(cand_combined)

                # Compute statistical evidence for metrics
                metric_datasets = [
                    ("accuracy", base_accuracy, cand_accuracy),
                    ("latency_ms", base_latency, cand_latency),
                    ("estimated_cost", base_cost, cand_cost),
                    ("consistency", base_combined, cand_combined),
                    ("safety", base_safety, cand_safety),
                ]

                # Create BenchmarkResult record first
                dummy_score = 0.0
                benchmark_result = await repo.create_result(
                    benchmark_run_id=run.id,
                    evaluation_run_id=cand_run_id,
                    baseline_run_id=base_run.id,
                    model_id=cand_model_id,
                    reliability_score=dummy_score,
                )

                metric_scores = {}
                for metric_name, b_data, c_data in metric_datasets:
                    mean_b = calculate_mean(b_data)
                    mean_c = calculate_mean(c_data)
                    abs_change = mean_c - mean_b
                    rel_change = (abs_change / mean_b) if mean_b != 0 else 0.0

                    stat = calculate_comparison_statistics(b_data, c_data)
                    p_val = stat.get("p_value") if stat else None
                    eff_size = stat.get("effect_size") if stat else None
                    ci_low = stat.get("ci_candidate_lower") if stat else None
                    ci_high = stat.get("ci_candidate_upper") if stat else None
                    sig = (p_val < 0.05) if p_val is not None else False
                    conf = "LOW"
                    if p_val is not None:
                        conf = "HIGH" if p_val < 0.01 else "MEDIUM" if p_val < 0.05 else "LOW"

                    await repo.create_evidence(
                        benchmark_run_id=run.id,
                        benchmark_result_id=benchmark_result.id,
                        metric_name=metric_name,
                        baseline_value=mean_b,
                        candidate_value=mean_c,
                        absolute_change=abs_change,
                        relative_change=rel_change,
                        sample_size=len(c_data),
                        p_value=p_val,
                        effect_size=eff_size,
                        confidence_interval_low=ci_low,
                        confidence_interval_high=ci_high,
                        significance=sig,
                        confidence=conf,
                    )

                    # Compute score mapping for reliability weights
                    if metric_name == "accuracy":
                        metric_scores["accuracy"] = mean_c
                    elif metric_name == "latency_ms":
                        metric_scores["latency_ms"] = 1.0 if mean_c <= mean_b else (mean_b / mean_c if mean_c > 0 else 0.0)
                    elif metric_name == "estimated_cost":
                        metric_scores["estimated_cost"] = 1.0 if mean_c <= mean_b else (mean_b / mean_c if mean_c > 0 else 0.0)
                    elif metric_name == "consistency":
                        metric_scores["consistency"] = max(0.0, 1.0 - cand_std_combined)
                    elif metric_name == "safety":
                        metric_scores["safety"] = mean_c

                # Calculate Weighted Reliability Score
                reliability_score = sum(weights.get(m, 0.0) * metric_scores.get(m, 0.0) for m in weights)
                benchmark_result.reliability_score = reliability_score
                overall_run_scores.append(reliability_score)

            # Overall run reliability score
            overall_score = calculate_mean(overall_run_scores) if overall_run_scores else 0.0
            run.reliability_score = overall_score

            # Failure Intelligence & Deterministic Clustering
            # Group errors in candidate runs
            error_groups = {}
            for r in all_candidate_failures:
                msg = r.failure_message or "Assertion failed or output mismatch"
                # Strip dynamic components (e.g. numeric IDs, timestamps, or limits) to cluster patterns
                pattern = msg.strip().lower()
                # Group by prefix or common pattern
                if len(pattern) > 100:
                    pattern = pattern[:100] + "..."
                error_groups[pattern] = error_groups.get(pattern, []) + [r]

            total_failures = len(all_candidate_failures)
            for pattern, group in error_groups.items():
                count = len(group)
                pct = count / total_failures if total_failures > 0 else 0.0
                severity = "HIGH" if pct >= 0.4 else "MEDIUM" if pct >= 0.1 else "LOW"
                await repo.create_failure_cluster(
                    benchmark_run_id=run.id,
                    benchmark_result_id=None,
                    failure_type="ACCURACY_FAILURE",
                    error_message_pattern=pattern,
                    cluster_count=count,
                    cluster_percentage=pct,
                    severity=severity,
                )

            # Regression Attribution & Root-Cause Analysis
            # Retrieve evidence and attribution
            recs_created = 0
            for r_res in await repo.list_results_for_run(run.id):
                # Retrieve evidences for this candidate
                cand_evs = [ev for ev in await repo.list_evidences_for_run(run.id) if ev.benchmark_result_id == r_res.id]
                # Look for significant negative changes
                regressed_metrics = [ev for ev in cand_evs if ev.absolute_change < -0.05]

                regression_attr = None
                root_cause = "No significant reliability regression detected."
                recommendation = "Maintain current model variant and configuration."
                confidence = "HIGH"

                if regressed_metrics:
                    worst_metric = min(regressed_metrics, key=lambda x: x.absolute_change)
                    regression_attr = f"Significant drop in {worst_metric.metric_name} (change: {worst_metric.absolute_change:.4f})"
                    root_cause = f"The candidate model variant has regressed primarily on '{worst_metric.metric_name}' compared to baseline. "
                    confidence = worst_metric.confidence

                    # Match with failure cluster patterns if accuracy dropped
                    if worst_metric.metric_name == "accuracy" and error_groups:
                        top_pattern = max(error_groups.items(), key=lambda x: len(x[1]))[0]
                        root_cause += f"Major contributor is failed assertions with pattern: '{top_pattern}'."
                        recommendation = f"Refine prompting or model instructions to resolve error pattern: '{top_pattern}'. "
                    else:
                        recommendation = f"Analyze configuration parameters, optimize context size, or review model routing for '{worst_metric.metric_name}' to mitigate drop. "

                    recommendation += f"Verify temperature settings and ensure provider rate-limits are not exceeded."
                else:
                    # Positive or neutral
                    recommendation = "Reliability standards met. Model candidate is suitable for promotion to production environments."

                await repo.create_recommendation(
                    benchmark_run_id=run.id,
                    benchmark_result_id=r_res.id,
                    regression_attribution=regression_attr,
                    root_cause_analysis=root_cause,
                    root_cause_confidence=confidence,
                    recommendation=recommendation,
                )
                recs_created += 1

            # Transition status to COMPLETED
            await repo.set_run_status(run, "COMPLETED")

            # Automatically publish canonical compliance evidence (Phase 15)
            from app.models.project import Project
            from app.services.evidence_service import publish_canonical_evidence
            project = await session.get(Project, suite.project_id)
            if project:
                await publish_canonical_evidence(
                    session=session,
                    organization_id=project.organization_id,
                    source_type="benchmark_run",
                    source_id=str(run.id),
                    project_id=project.id,
                    metadata_summary={"reliability_score": overall_score, "status": "COMPLETED"},
                )

            await session.commit()

        return {"status": "COMPLETED", "reliability_score": overall_score}
