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


async def _periodic_scheduler(alert_interval_seconds: int = 60, retention_interval_seconds: int = 3600) -> None:
    """Run periodic Phase 8 background jobs on a fixed cadence.

    - ``evaluate_alerts``: evaluate alert rules against sliding-window metrics,
      trigger/deduplicate/resolve incidents and dispatch notifications.
    - ``clean_observability_retention``: delete expired traces/spans according
      to each project's retention policy.

    A daemon task is deliberately used so a slow job never blocks queue
    processing. Exceptions are caught so the scheduler keeps running.
    """
    from app.workers.tasks import evaluate_alerts, clean_observability_retention

    next_alerts = next_retention = asyncio.get_event_loop().time()

    while True:
        now = asyncio.get_event_loop().time()
        try:
            if now >= next_alerts:
                logger.info("periodic: evaluating alert rules")
                await evaluate_alerts("periodic-evaluate-alerts", {})
                next_alerts = now + alert_interval_seconds
            if now >= next_retention:
                logger.info("periodic: cleaning observability retention")
                await clean_observability_retention("periodic-clean-retention", {})
                next_retention = now + retention_interval_seconds
        except Exception:  # pragma: no cover - defensive
            logger.exception("periodic scheduler job failed")
        await asyncio.sleep(min(alert_interval_seconds, retention_interval_seconds, 5))


async def run_worker(once: bool = False, poll_seconds: float = 1.0) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    queue = build_queue()
    logger.info("worker starting", extra={"queue": type(queue).__name__})
    await _connect(queue)

    scheduler_task = None
    if not once:
        scheduler_task = asyncio.create_task(_periodic_scheduler())

    concurrency_limit = getattr(settings, "worker_concurrency", 10)
    sem = asyncio.Semaphore(concurrency_limit)
    active_tasks: set[asyncio.Task] = set()

    try:
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

            if not once:
                await sem.acquire()

            item: tuple[str, str, dict[str, Any]] | None = None
            try:
                item = await queue.dequeue(timeout=poll_seconds)
            except Exception:
                logger.exception("dequeue failed")
                if not once:
                    sem.release()
                await asyncio.sleep(poll_seconds)
                continue

            if item is None:
                if not once:
                    sem.release()
                if once:
                    break
                continue

            job_id, task_name, payload = item
            handler = TASK_REGISTRY.get(task_name)
            if handler is None:
                logger.error("unknown task", extra={"task": task_name, "job_id": job_id})
                queue_jobs_failed_total.inc()
                if not once:
                    sem.release()
                continue

            async def execute_task(jid: str, tname: str, pload: dict[str, Any], semaphore_acquired: bool) -> None:
                try:
                    result = await handler(jid, pload)
                    logger.info(
                        "job completed",
                        extra={"job_id": jid, "task": tname, "result": result},
                    )
                except NotImplementedError:
                    logger.warning("task not implemented in phase 0", extra={"task": tname})
                except Exception:
                    queue_jobs_failed_total.inc()
                    logger.exception("job failed", extra={"job_id": jid, "task": tname})
                finally:
                    if semaphore_acquired:
                        sem.release()

            if once:
                await execute_task(job_id, task_name, payload, semaphore_acquired=False)
                break
            else:
                task = asyncio.create_task(execute_task(job_id, task_name, payload, semaphore_acquired=True))
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)
    finally:
        if scheduler_task is not None:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Graceful shutdown: await all active tasks
        if active_tasks:
            logger.info("worker shutting down: waiting for active tasks to complete", extra={"active_count": len(active_tasks)})
            await asyncio.gather(*active_tasks, return_exceptions=True)
            logger.info("all active worker tasks completed")
            
        await queue.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
