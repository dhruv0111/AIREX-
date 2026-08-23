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


TASK_REGISTRY: dict[str, TaskHandler] = {
    "test_job": test_job,
    "run_evaluation": run_evaluation,
    "generate_test_cases": generate_test_cases,
}
