"""Worker process (spec §42–§44, AT-023/024; Phase 3 §48–§50).

Runs:  python -m app.workers.worker
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.metrics import queue_jobs_failed_total
from app.db.session import get_session_factory
from app.evaluations.runner import recover_stale_runs
from app.generation.runner import recover_stale_generations
from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue
from app.workers.tasks import TASK_REGISTRY

logger = logging.getLogger("airex.workers")


def build_queue() -> TaskQueue:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        return InMemoryTaskQueue()
    return RedisTaskQueue(settings.redis_url)


async def _connect(queue: TaskQueue) -> None:
    connect = getattr(queue, "connect", None)
    if connect is not None:
        await connect()


async def run_worker(once: bool = False, poll_seconds: float = 1.0) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    queue = build_queue()
    logger.info("worker starting", extra={"queue": type(queue).__name__})
    await _connect(queue)

    while True:
        # Crash/stale-run recovery (§50): mark RUNNING evaluations with a stale
        # heartbeat as FAILED so they are never permanently stuck.
        try:
            await recover_stale_runs(get_session_factory())
        except Exception:  # pragma: no cover - defensive
            logger.exception("stale-run recovery failed")
        # Phase 5: recover RUNNING test-generation requests with a stale heartbeat.
        try:
            await recover_stale_generations(get_session_factory())
        except Exception:  # pragma: no cover - defensive
            logger.exception("stale-generation recovery failed")

        item: tuple[str, str, dict[str, Any]] | None = await queue.dequeue(timeout=poll_seconds)
        if item is None:
            if once:
                break
            continue
        job_id, task_name, payload = item
        handler = TASK_REGISTRY.get(task_name)
        if handler is None:
            logger.error("unknown task", extra={"task": task_name, "job_id": job_id})
            queue_jobs_failed_total.inc()
            continue
        try:
            result = await handler(job_id, payload)
            logger.info(
                "job completed",
                extra={"job_id": job_id, "task": task_name, "result": result},
            )
        except NotImplementedError:
            logger.warning("task not implemented in phase 0", extra={"task": task_name})
        except Exception:
            queue_jobs_failed_total.inc()
            logger.exception("job failed", extra={"job_id": job_id, "task": task_name})
        if once:
            break

    await queue.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
