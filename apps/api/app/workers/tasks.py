"""Task registry (spec §24, AT-024; Phase 3 §48).

Each task is an async handler (job_id, payload) -> dict result. Phase 3 adds the
``run_evaluation`` task executed by the evaluation worker.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("airex.workers.tasks")

TaskHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


async def test_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Test task used by AT-024 (receive → execute → complete)."""
    logger.info("test_job executed", extra={"job_id": job_id, "payload": payload})
    return {"job_id": job_id, "status": "completed", "payload": payload}


async def run_evaluation(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute an evaluation run (Phase 3 §48).

    Runs stale-run recovery first, then drives QUEUED → RUNNING → COMPLETED/FAILED
    via the EvaluationRunner. Duplicate/terminal jobs are idempotent (§49).
    """
    from uuid import UUID

    from app.db.session import get_session_factory
    from app.evaluations.runner import EvaluationRunner, recover_stale_runs

    run_id_raw = payload.get("evaluation_run_id")
    if not run_id_raw:
        raise ValueError("Missing evaluation_run_id in job payload.")

    session_factory = get_session_factory()
    try:
        await recover_stale_runs(session_factory)
    except Exception:  # pragma: no cover - defensive
        logger.exception("stale-run recovery failed")

    runner = EvaluationRunner(session_factory)
    result = await runner.run(UUID(run_id_raw))
    logger.info("evaluation job completed", extra={"job_id": job_id, "result": result})
    return result


async def generate_test_cases(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a test-generation request (Phase 5).

    Runs stale-generation recovery first, then drives
    QUEUED → RUNNING → COMPLETED/FAILED via the GenerationRunner. Duplicate /
    terminal jobs are idempotent (fingerprint-based dedup).
    """
    from uuid import UUID

    from app.db.session import get_session_factory
    from app.generation.runner import GenerationRunner, recover_stale_generations

    request_id_raw = payload.get("generation_request_id")
    if not request_id_raw:
        raise ValueError("Missing generation_request_id in job payload.")

    session_factory = get_session_factory()
    try:
        await recover_stale_generations(session_factory)
    except Exception:  # pragma: no cover - defensive
        logger.exception("stale-generation recovery failed")

    runner = GenerationRunner(session_factory)
    result = await runner.run(UUID(request_id_raw))
    logger.info("generation job completed", extra={"job_id": job_id, "result": result})
    return result


async def run_experiment(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute an experiment run (Phase 6).

    Runs stale-experiment recovery first, then drives QUEUED → RUNNING → COMPLETED/FAILED
    via the ExperimentRunner. Duplicate / terminal jobs are idempotent.
    """
    from uuid import UUID

    from app.db.session import get_session_factory
    from app.evaluations.experiment_runner import ExperimentRunner, recover_stale_experiments

    run_id_raw = payload.get("experiment_run_id")
    if not run_id_raw:
        raise ValueError("Missing experiment_run_id in job payload.")

    session_factory = get_session_factory()
    try:
        await recover_stale_experiments(session_factory)
    except Exception:  # pragma: no cover - defensive
        logger.exception("stale-experiment recovery failed")

    runner = ExperimentRunner(session_factory)
    result = await runner.run(UUID(run_id_raw))
    logger.info("experiment job completed", extra={"job_id": job_id, "result": result})
    return result


async def ingest_observability(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Asynchronously ingest a batch of traces and spans."""
    from uuid import UUID
    from app.db.session import get_session_factory
    from app.services.observability import ObservabilityService

    project_id_raw = payload.get("project_id")
    org_id_raw = payload.get("org_id")
    traces = payload.get("traces", [])
    spans = payload.get("spans", [])

    if not project_id_raw or not org_id_raw:
        raise ValueError("Missing project_id or org_id in payload.")

    session_factory = get_session_factory()
    async with session_factory() as session:
        service = ObservabilityService(session)
        result = await service.ingest_batch(
            project_id=UUID(project_id_raw),
            org_id=UUID(org_id_raw),
            traces=traces,
            spans=spans,
        )
        logger.info("observability ingestion job completed", extra={"job_id": job_id, "result": result})
        return result


async def clean_observability_retention_for_session(session) -> dict[str, int]:
    """Delete expired traces/spans using the provided session (testable in isolation)."""
    from datetime import datetime, timedelta, UTC
    from sqlalchemy import select, delete
    from app.models.project import Project
    from app.models.trace import Trace, Span

    deleted_traces = 0
    deleted_spans = 0

    # Get all projects
    res = await session.execute(select(Project))
    projects = res.scalars().all()

    for p in projects:
        settings = p.settings or {}
        retention_days = settings.get("retention_days")
        if not retention_days:
            continue

        try:
            days = int(retention_days)
        except ValueError:
            continue

        # Handle timezone-aware cutoff
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Find trace IDs to delete first (so we can delete spans)
        stmt_traces = select(Trace.trace_id).where(
            Trace.project_id == p.id,
            Trace.start_time < cutoff
        )
        res_trace_ids = await session.execute(stmt_traces)
        trace_ids = list(res_trace_ids.scalars().all())

        if trace_ids:
            # Delete Spans belonging to these traces
            stmt_del_spans = delete(Span).where(Span.trace_id.in_(trace_ids))
            res_spans = await session.execute(stmt_del_spans)
            deleted_spans += res_spans.rowcount

            # Delete Traces
            stmt_del_traces = delete(Trace).where(Trace.trace_id.in_(trace_ids))
            res_traces = await session.execute(stmt_del_traces)
            deleted_traces += res_traces.rowcount

    await session.commit()
    return {
        "deleted_traces": deleted_traces,
        "deleted_spans": deleted_spans,
    }


async def clean_observability_retention(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Clean up expired production traces and spans based on project policies."""
    from app.db.session import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        return await clean_observability_retention_for_session(session)


async def evaluate_alerts(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Periodically evaluate alert rules and update metrics/incidents."""
    from app.db.session import get_session_factory
    from app.evaluations.alert_engine import evaluate_alert_rules

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await evaluate_alert_rules(session)
        logger.info("alerts evaluation job completed", extra={"job_id": job_id, "result": result})
        return result


async def run_benchmark(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a benchmark run (Phase 9)."""
    from uuid import UUID
    from app.db.session import get_session_factory
    from app.evaluations.benchmark_runner import BenchmarkRunner

    run_id_raw = payload.get("benchmark_run_id")
    if not run_id_raw:
        raise ValueError("Missing benchmark_run_id in job payload.")

    session_factory = get_session_factory()
    runner = BenchmarkRunner(session_factory)
    result = await runner.run(UUID(run_id_raw))
    logger.info("benchmark job completed", extra={"job_id": job_id, "result": result})
    return result


TASK_REGISTRY: dict[str, TaskHandler] = {
    "test_job": test_job,
    "run_evaluation": run_evaluation,
    "generate_test_cases": generate_test_cases,
    "run_experiment": run_experiment,
    "ingest_observability": ingest_observability,
    "clean_observability_retention": clean_observability_retention,
    "evaluate_alerts": evaluate_alerts,
    "run_benchmark": run_benchmark,
}
