"""Evidence aggregation service for Phase 10 Intelligence & Deployment Decision Layer."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
import math
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EvaluationRun,
    ExperimentRun,
    ExperimentComparison,
    Regression,
    QualityGateResult,
    BenchmarkRun,
    BenchmarkResult,
    ReliabilityEvidence,
    FailureCluster,
    Trace,
    Span,
    Alert,
    AlertRule,
    Environment,
    AgentRun,
)


class EvidenceAggregator:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def aggregate(
        self,
        *,
        project_id: UUID,
        environment_id: UUID,
        model_id: UUID,
        provider_id: UUID,
        max_age_days: int = 14,
    ) -> list[dict[str, Any]]:
        """Collect canonical evidence from evaluations, experiments, benchmarks, observability, and alerts."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=max_age_days)
        evidences: list[dict[str, Any]] = []

        # Get environment object to resolve name if needed
        env_obj = await self._session.get(Environment, environment_id)
        env_name = env_obj.name.lower() if env_obj else None

        # ------------------------------------------------------------- 1. Evaluation Evidence
        eval_stmt = (
            select(EvaluationRun)
            .where(
                and_(
                    EvaluationRun.project_id == project_id,
                    EvaluationRun.model_id == model_id,
                    EvaluationRun.status == "COMPLETED",
                )
            )
            .order_by(desc(EvaluationRun.completed_at), desc(EvaluationRun.created_at))
            .limit(1)
        )
        eval_res = await self._session.execute(eval_stmt)
        eval_run = eval_res.scalar_one_or_none()

        if eval_run:
            total = eval_run.total_tests or 0
            passed = eval_run.passed_tests or 0
            failed = eval_run.failed_tests or 0
            score = (passed / total * 100.0) if total > 0 else 0.0
            fresh_ts = eval_run.completed_at or eval_run.created_at
            # Make sure timezone aware
            if fresh_ts and fresh_ts.tzinfo is None:
                fresh_ts = fresh_ts.replace(tzinfo=UTC)
            is_fresh = fresh_ts >= cutoff if fresh_ts else False

            evidences.append({
                "source_type": "EVALUATION",
                "source_id": str(eval_run.id),
                "environment_id": eval_run.environment_id,
                "methodology_version": "1.0",
                "freshness_timestamp": fresh_ts,
                "is_fresh": is_fresh,
                "summary": {
                    "evaluation_run_id": str(eval_run.id),
                    "dataset_version_id": str(eval_run.dataset_version_id) if eval_run.dataset_version_id else None,
                    "total_tests": total,
                    "passed_tests": passed,
                    "failed_tests": failed,
                    "error_tests": eval_run.error_tests or 0,
                    "accuracy_score": round(score, 2),
                    "metrics": eval_run.metrics or {},
                },
            })

        # ------------------------------------------------------------- 2. Experiment Evidence
        # Find latest completed experiment run involving this model
        exp_stmt = (
            select(ExperimentRun)
            .join(EvaluationRun, ExperimentRun.candidate_run_id == EvaluationRun.id)
            .where(
                and_(
                    EvaluationRun.project_id == project_id,
                    EvaluationRun.model_id == model_id,
                    ExperimentRun.status == "COMPLETED",
                )
            )
            .order_by(desc(ExperimentRun.completed_at), desc(ExperimentRun.created_at))
            .limit(1)
        )
        exp_res = await self._session.execute(exp_stmt)
        exp_run = exp_res.scalar_one_or_none()

        # Fallback: any completed experiment in project
        if not exp_run:
            exp_fallback = (
                select(ExperimentRun)
                .join(EvaluationRun, ExperimentRun.candidate_run_id == EvaluationRun.id)
                .where(
                    and_(
                        EvaluationRun.project_id == project_id,
                        ExperimentRun.status == "COMPLETED",
                    )
                )
                .order_by(desc(ExperimentRun.completed_at), desc(ExperimentRun.created_at))
                .limit(1)
            )
            exp_res2 = await self._session.execute(exp_fallback)
            exp_run = exp_res2.scalar_one_or_none()

        if exp_run:
            fresh_ts = exp_run.completed_at or exp_run.created_at
            if fresh_ts and fresh_ts.tzinfo is None:
                fresh_ts = fresh_ts.replace(tzinfo=UTC)
            is_fresh = fresh_ts >= cutoff if fresh_ts else False

            # Query regressions
            comp_stmt = select(ExperimentComparison).where(ExperimentComparison.run_id == exp_run.id)
            comp_res = await self._session.execute(comp_stmt)
            comparisons = list(comp_res.scalars().all())
            comp_ids = [c.id for c in comparisons]

            regressions: list[Regression] = []
            if comp_ids:
                reg_stmt = select(Regression).where(Regression.comparison_id.in_(comp_ids))
                reg_res = await self._session.execute(reg_stmt)
                regressions = list(reg_res.scalars().all())

            # Severity ordering: CRITICAL > HIGH > MEDIUM > LOW > NONE
            severities = [r.severity.upper() for r in regressions]
            max_sev = "NONE"
            for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                if s in severities:
                    max_sev = s
                    break

            # Quality gate results
            qg_stmt = select(QualityGateResult).where(QualityGateResult.run_id == exp_run.id)
            qg_res = await self._session.execute(qg_stmt)
            qg_results = list(qg_res.scalars().all())
            all_gates_pass = all(q.status.upper() == "PASS" for q in qg_results) if qg_results else True

            evidences.append({
                "source_type": "EXPERIMENT",
                "source_id": str(exp_run.id),
                "environment_id": None,
                "methodology_version": "1.0",
                "freshness_timestamp": fresh_ts,
                "is_fresh": is_fresh,
                "summary": {
                    "experiment_run_id": str(exp_run.id),
                    "regression_count": len(regressions),
                    "max_regression_severity": max_sev,
                    "regressions": [
                        {
                            "metric_name": r.metric_name,
                            "severity": r.severity,
                            "baseline": r.baseline_value,
                            "candidate": r.candidate_value,
                        }
                        for r in regressions
                    ],
                    "quality_gates_count": len(qg_results),
                    "quality_gates_passed": all_gates_pass,
                },
            })

        # ------------------------------------------------------------- 3. Benchmark Evidence
        # Find latest completed benchmark result for this model
        bench_stmt = (
            select(BenchmarkResult)
            .join(BenchmarkRun, BenchmarkResult.benchmark_run_id == BenchmarkRun.id)
            .where(
                and_(
                    BenchmarkResult.model_id == model_id,
                    BenchmarkRun.status == "COMPLETED",
                )
            )
            .order_by(desc(BenchmarkResult.created_at))
            .limit(1)
        )
        bench_res = await self._session.execute(bench_stmt)
        bench_result = bench_res.scalar_one_or_none()

        bench_run: BenchmarkRun | None = None
        if bench_result:
            bench_run = await self._session.get(BenchmarkRun, bench_result.benchmark_run_id)
        else:
            # Fallback: latest completed benchmark run in project
            run_stmt = (
                select(BenchmarkRun)
                .where(
                    and_(
                        BenchmarkRun.status == "COMPLETED",
                    )
                )
                .order_by(desc(BenchmarkRun.completed_at), desc(BenchmarkRun.created_at))
                .limit(1)
            )
            run_res = await self._session.execute(run_stmt)
            bench_run = run_res.scalar_one_or_none()

        if bench_run:
            fresh_ts = bench_run.completed_at or bench_run.created_at
            if fresh_ts and fresh_ts.tzinfo is None:
                fresh_ts = fresh_ts.replace(tzinfo=UTC)
            is_fresh = fresh_ts >= cutoff if fresh_ts else False

            # Query statistical reliability evidences for this run
            rel_stmt = select(ReliabilityEvidence).where(ReliabilityEvidence.benchmark_run_id == bench_run.id)
            rel_res = await self._session.execute(rel_stmt)
            rel_evs = list(rel_res.scalars().all())

            # Query failure clusters
            fc_stmt = select(FailureCluster).where(FailureCluster.benchmark_run_id == bench_run.id)
            fc_res = await self._session.execute(fc_stmt)
            clusters = list(fc_res.scalars().all())

            # Best sample size & confidence from reliability evidences
            sample_size = max([e.sample_size for e in rel_evs], default=0)
            p_values = [e.p_value for e in rel_evs if e.p_value is not None]
            min_p_value = min(p_values) if p_values else None
            # Confidence is 1.0 - p_value if p_value exists, or 0.95 fallback
            statistical_confidence = (1.0 - min_p_value) if min_p_value is not None else 0.95

            score = bench_result.reliability_score if bench_result else (bench_run.reliability_score or 0.0)

            evidences.append({
                "source_type": "BENCHMARK",
                "source_id": str(bench_run.id),
                "environment_id": None,
                "methodology_version": bench_run.methodology_version or "1.0",
                "freshness_timestamp": fresh_ts,
                "is_fresh": is_fresh,
                "summary": {
                    "benchmark_run_id": str(bench_run.id),
                    "reliability_score": round(score, 2),
                    "sample_size": sample_size,
                    "p_value": min_p_value,
                    "statistical_confidence": round(statistical_confidence, 4),
                    "failure_clusters_count": len(clusters),
                    "failure_clusters": [
                        {
                            "failure_type": c.failure_type,
                            "cluster_count": c.cluster_count,
                            "cluster_percentage": c.cluster_percentage,
                            "severity": c.severity,
                        }
                        for c in clusters
                    ],
                },
            })

        # ------------------------------------------------------------- 4. Observability Evidence
        # Aggregate traces for this project in the given environment
        trace_stmt = select(Trace).where(
            and_(
                Trace.project_id == project_id,
                Trace.start_time >= cutoff,
            )
        )
        if env_name:
            trace_stmt = trace_stmt.where(func.lower(Trace.environment) == env_name)

        trace_res = await self._session.execute(trace_stmt)
        traces = list(trace_res.scalars().all())

        if traces:
            total_traces = len(traces)
            error_traces = sum(1 for t in traces if t.status == "ERROR" or t.error)
            error_rate = error_traces / total_traces if total_traces > 0 else 0.0

            durations = [t.duration_ms for t in traces if t.duration_ms is not None and t.duration_ms >= 0]
            avg_latency = sum(durations) / len(durations) if durations else 0.0
            sorted_durations = sorted(durations)
            p95_idx = int(math.ceil(0.95 * len(sorted_durations))) - 1
            p95_latency = sorted_durations[max(0, p95_idx)] if sorted_durations else 0.0

            latest_trace_time = max((t.start_time for t in traces), default=now)
            if latest_trace_time.tzinfo is None:
                latest_trace_time = latest_trace_time.replace(tzinfo=UTC)

            evidences.append({
                "source_type": "OBSERVABILITY",
                "source_id": f"traces-{project_id}-{env_name or 'all'}",
                "environment_id": environment_id,
                "methodology_version": "1.0",
                "freshness_timestamp": latest_trace_time,
                "is_fresh": latest_trace_time >= cutoff,
                "summary": {
                    "total_requests": total_traces,
                    "error_count": error_traces,
                    "error_rate": round(error_rate, 4),
                    "availability": round(1.0 - error_rate, 4),
                    "avg_latency_ms": round(avg_latency, 2),
                    "p95_latency_ms": round(p95_latency, 2),
                    "cost": 0.0,
                },
            })

        # ------------------------------------------------------------- 5. Alerts Evidence
        # Query active / non-resolved alerts for this project
        alert_stmt = (
            select(Alert)
            .where(
                and_(
                    Alert.project_id == project_id,
                    Alert.status.in_(["TRIGGERED", "ACKNOWLEDGED"]),
                )
            )
        )
        alert_res = await self._session.execute(alert_stmt)
        active_alerts = list(alert_res.scalars().all())

        critical_count = sum(1 for a in active_alerts if a.severity.lower() == "critical")
        latest_alert_ts = max((a.last_seen_at for a in active_alerts), default=now)
        if latest_alert_ts.tzinfo is None:
            latest_alert_ts = latest_alert_ts.replace(tzinfo=UTC)

        evidences.append({
            "source_type": "ALERT",
            "source_id": f"alerts-{project_id}",
            "environment_id": environment_id,
            "methodology_version": "1.0",
            "freshness_timestamp": latest_alert_ts,
            "is_fresh": True,
            "summary": {
                "total_active_alerts": len(active_alerts),
                "critical_alerts_count": critical_count,
                "alerts": [
                    {
                        "id": str(a.id),
                        "severity": a.severity,
                        "status": a.status,
                        "message": a.message,
                        "observed_value": a.observed_value,
                    }
                    for a in active_alerts
                ],
            },
        })

        # ------------------------------------------------------------- 6. Agent Evaluation Evidence (Phase 11)
        agent_stmt = (
            select(AgentRun)
            .where(
                and_(
                    AgentRun.project_id == project_id,
                    AgentRun.status == "COMPLETED",
                )
            )
            .order_by(desc(AgentRun.completed_at), desc(AgentRun.created_at))
            .limit(1)
        )
        agent_res = await self._session.execute(agent_stmt)
        latest_agent_run = agent_res.scalar_one_or_none()

        if latest_agent_run:
            fresh_ts = latest_agent_run.completed_at or latest_agent_run.created_at
            if fresh_ts and fresh_ts.tzinfo is None:
                fresh_ts = fresh_ts.replace(tzinfo=UTC)
            is_fresh = fresh_ts >= cutoff if fresh_ts else False

            evidences.append({
                "source_type": "AGENT_EVALUATION",
                "source_id": str(latest_agent_run.id),
                "environment_id": latest_agent_run.environment_id,
                "methodology_version": "1.0",
                "freshness_timestamp": fresh_ts,
                "is_fresh": is_fresh,
                "summary": {
                    "agent_id": str(latest_agent_run.agent_id),
                    "agent_run_id": str(latest_agent_run.id),
                    "agent_version": latest_agent_run.agent_version,
                    "reliability_score": latest_agent_run.reliability_score,
                    "goal_completion_status": latest_agent_run.goal_completion_status,
                    "safety_violations": latest_agent_run.safety_violations,
                    "loops_detected": latest_agent_run.loops_detected,
                    "total_steps": latest_agent_run.total_steps,
                    "total_tool_calls": latest_agent_run.total_tool_calls,
                },
            })

        return evidences
