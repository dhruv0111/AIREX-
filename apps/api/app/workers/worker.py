"""Worker process (spec §42–§44, AT-023/024; Phase 3 §48–§50; Phase 12).

Runs:  python -m app.workers.worker
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.metrics import queue_jobs_failed_total
from app.db.session import get_session_factory
from app.evaluations.runner import recover_stale_runs
from app.generation.runner import recover_stale_generations
from app.models.worker import TaskFailure, WorkerHeartbeat
from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue
from app.workers.tasks import TASK_REGISTRY

logger = logging.getLogger("airex.workers")

_PROCESSED_JOBS: set[str] = set()


def reset_processed_jobs() -> None:
    _PROCESSED_JOBS.clear()


def build_queue() -> TaskQueue:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        return InMemoryTaskQueue()
    return RedisTaskQueue(settings.redis_url)


async def _connect(queue: TaskQueue) -> None:
    connect = getattr(queue, "connect", None)
    if connect is not None:
        await connect()


async def _record_heartbeat(worker_id: str, hostname: str, pid: int, active_count: int, started_at: datetime, status: str = "ACTIVE") -> None:
    """Record or update worker heartbeat in database."""
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            stmt = select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == worker_id)
            res = await session.execute(stmt)
            entry = res.scalars().first()
            now = datetime.now(UTC)
            if entry is None:
                entry = WorkerHeartbeat(
                    worker_id=worker_id,
                    hostname=hostname,
                    pid=pid,
                    status=status,
                    active_jobs_count=active_count,
                    heartbeat_at=now,
                    started_at=started_at,
                )
                session.add(entry)
            else:
                entry.status = status
                entry.active_jobs_count = active_count
                entry.heartbeat_at = now
            await session.commit()
    except Exception:
        logger.debug("Could not record worker heartbeat")


async def _record_task_failure(job_id: str, task_name: str, payload: dict[str, Any], error_message: str) -> None:
    """Dead-letter failure recording preventing silent task loss."""
    session_factory = get_session_factory()
    try:
        async with session_factory() as session:
            failure = TaskFailure(
                job_id=job_id,
                task_name=task_name,
                payload=payload,
                error_message=error_message[:2000],
                failed_at=datetime.now(UTC),
            )
            session.add(failure)
            await session.commit()
    except Exception:
        logger.exception("Failed to record dead-letter task failure")


async def _worker_heartbeat_loop(worker_id: str, hostname: str, pid: int, started_at: datetime, active_tasks: set[asyncio.Task], interval_seconds: int = 5) -> None:
    """Emits periodic worker heartbeat on a 5-second interval."""
    while True:
        try:
            await _record_heartbeat(worker_id, hostname, pid, len(active_tasks), started_at, status="ACTIVE")
        except Exception:
            pass
        await asyncio.sleep(interval_seconds)


async def _periodic_scheduler(alert_interval_seconds: int = 60, retention_interval_seconds: int = 3600) -> None:
    """Run periodic Phase 8 & Phase 14/15 background jobs on a fixed cadence."""
    from app.workers.tasks import evaluate_alerts, clean_observability_retention, execute_centralized_retention

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
                logger.info("periodic: executing centralized compliance retention")
                await execute_centralized_retention("periodic-clean-centralized-retention", {"dry_run": False})
                next_retention = now + retention_interval_seconds
        except Exception:  # pragma: no cover - defensive
            logger.exception("periodic scheduler job failed")
        await asyncio.sleep(min(alert_interval_seconds, retention_interval_seconds, 5))


async def run_worker(once: bool = False, poll_seconds: float = 1.0) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    queue = build_queue()

    hostname = socket.gethostname()
    pid = os.getpid()
    worker_id = f"worker-{hostname}-{pid}-{uuid4().hex[:6]}"
    started_at = datetime.now(UTC)

    logger.info("worker starting", extra={"queue": type(queue).__name__, "worker_id": worker_id})
    await _connect(queue)

    scheduler_task = None
    heartbeat_task = None
    if not once:
        scheduler_task = asyncio.create_task(_periodic_scheduler())

    concurrency_limit = getattr(settings, "worker_concurrency", 10)
    sem = asyncio.Semaphore(concurrency_limit)
    active_tasks: set[asyncio.Task] = set()
    processed_jobs = _PROCESSED_JOBS

    max_retries_default = getattr(settings, "worker_max_retries", 3)
    backoff_base = getattr(settings, "worker_retry_backoff_base", 2.0)
    task_timeout = getattr(settings, "worker_task_timeout_seconds", 300)

    if not once:
        heartbeat_task = asyncio.create_task(
            _worker_heartbeat_loop(worker_id, hostname, pid, started_at, active_tasks)
        )

    try:
        while True:
            # Crash/stale-run recovery (§50)
            try:
                await recover_stale_runs(get_session_factory())
            except Exception:
                logger.exception("stale-run recovery failed")
            try:
                await recover_stale_generations(get_session_factory())
            except Exception:
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

            # Idempotency check: prevent duplicate task execution
            idempotency_key = payload.get("idempotency_key") or job_id
            if idempotency_key in processed_jobs:
                logger.info("skipping already processed job", extra={"job_id": job_id, "idempotency_key": idempotency_key})
                if not once:
                    sem.release()
                continue

            handler = TASK_REGISTRY.get(task_name)
            if handler is None:
                logger.error("unknown task", extra={"task": task_name, "job_id": job_id})
                queue_jobs_failed_total.inc()
                await queue.enqueue_dlq(job_id, task_name, payload, f"Unknown task: {task_name}")
                await _record_task_failure(job_id, task_name, payload, f"Unknown task: {task_name}")
                if not once:
                    sem.release()
                continue

            async def execute_task(jid: str, tname: str, pload: dict[str, Any], semaphore_acquired: bool) -> None:
                attempts = pload.get("_attempts", 0) + 1
                max_retries = pload.get("_max_retries", max_retries_default)
                pload["_attempts"] = attempts

                try:
                    # Enforce task execution timeout
                    result = await asyncio.wait_for(handler(jid, pload), timeout=task_timeout)
                    processed_jobs.add(idempotency_key)
                    # Cap in-memory set size
                    if len(processed_jobs) > 10000:
                        processed_jobs.clear()

                    logger.info(
                        "job completed",
                        extra={"job_id": jid, "task": tname, "attempts": attempts, "result": result},
                    )
                except NotImplementedError:
                    logger.warning("task not implemented in phase 0", extra={"task": tname})
                    processed_jobs.add(idempotency_key)
                except Exception as exc:
                    error_msg = str(exc)
                    if attempts < max_retries:
                        backoff = (backoff_base ** (attempts - 1)) * 0.2
                        logger.warning(
                            "job failed, scheduling retry",
                            extra={"job_id": jid, "task": tname, "attempt": attempts, "max_retries": max_retries, "backoff": backoff, "error": error_msg},
                        )
                        await asyncio.sleep(backoff)
                        # Re-enqueue for retry
                        await queue.enqueue(tname, pload, max_retries=max_retries)
                    else:
                        # Retry exhaustion -> Route to Dead-Letter Queue (DLQ)
                        queue_jobs_failed_total.inc()
                        logger.error(
                            "job exhausted all retries, moved to DLQ",
                            extra={"job_id": jid, "task": tname, "attempts": attempts, "error": error_msg},
                        )
                        await queue.enqueue_dlq(jid, tname, pload, f"Exhausted {max_retries} retries: {error_msg}")
                        await _record_task_failure(jid, tname, pload, f"Exhausted {max_retries} retries: {error_msg}")
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

        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        # Graceful shutdown: await all active tasks
        if active_tasks:
            logger.info("worker shutting down: waiting for active tasks to complete", extra={"active_count": len(active_tasks)})
            await asyncio.gather(*active_tasks, return_exceptions=True)
            logger.info("all active worker tasks completed")

        # Mark worker STOPPED in database
        try:
            await _record_heartbeat(worker_id, hostname, pid, 0, started_at, status="STOPPED")
        except Exception:
            pass

        await queue.close()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
