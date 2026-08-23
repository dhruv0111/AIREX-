"""Stack verification (AT-002/003/023/024) against real PostgreSQL + Redis.

Run with DATABASE_URL and REDIS_URL pointing at the Docker test stack:
    set DATABASE_URL=postgresql+asyncpg://airex:airex@localhost:5433/airex_test
    set REDIS_URL=redis://localhost:6380/0
    python scripts/verify_stack.py
"""
from __future__ import annotations

import asyncio
import os
import sys

from app.core.config import Settings


async def verify_postgres(settings: Settings) -> None:
    import asyncpg

    # Parse URL into connection params (simple DSN).
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn, timeout=5)
    try:
        value = await conn.fetchval("SELECT 1")
        assert value == 1, "SELECT 1 failed"
    finally:
        await conn.close()
    print("AT-002  POSTGRES_CONNECTIVITY  PASS")


async def verify_redis(settings: Settings) -> None:
    import redis as redis_lib

    client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=5)
    assert client.ping(), "redis ping failed"
    print("AT-003  REDIS_CONNECTIVITY      PASS")


async def verify_worker(settings: Settings) -> None:
    from app.workers.queue import RedisTaskQueue
    from app.workers.tasks import TASK_REGISTRY

    queue = RedisTaskQueue(settings.redis_url, queue_name="airex:verify")
    await queue.connect()
    job_id = await queue.enqueue("test_job", {"smoke": True})
    item = await queue.dequeue(timeout=5)
    assert item is not None, "no job dequeued"
    got_job_id, task, payload = item
    assert got_job_id == job_id and task == "test_job"
    result = await TASK_REGISTRY[task](got_job_id, payload)
    assert result["status"] == "completed"
    print("AT-023  WORKER_STARTUP          PASS")
    print("AT-024  QUEUE_ROUNDTRIP         PASS")
    await queue.close()


async def main() -> None:
    settings = Settings()
    await verify_postgres(settings)
    await verify_redis(settings)
    await verify_worker(settings)
    print("STACK VERIFICATION: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
