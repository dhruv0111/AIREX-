"""Task queue abstraction (spec §2.3, §23–§24, AT-023/024).

The queue is isolated behind a ``TaskQueue`` protocol so the implementation can
be replaced later (Celery/RQ/Arq) without touching producers or the worker
(ADR-005). Phase 0 ships a Redis-list-backed implementation and an in-memory
implementation for tests.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Protocol

from app.core.metrics import queue_jobs_total


class TaskQueue(Protocol):
    async def enqueue(self, task: str, payload: dict[str, Any]) -> str: ...

    async def dequeue(self, timeout: float = 1.0) -> tuple[str, str, dict[str, Any]] | None: ...

    async def close(self) -> None: ...


class RedisTaskQueue:
    """Redis list-backed queue. Message = JSON {job_id, task, payload}."""

    def __init__(self, redis_url: str, queue_name: str = "airex:queue") -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._redis: Any = None

    async def connect(self) -> None:
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()

    async def enqueue(self, task: str, payload: dict[str, Any]) -> str:
        await self.connect()
        job_id = str(uuid.uuid4())
        message = json.dumps({"job_id": job_id, "task": task, "payload": payload})
        await self._redis.rpush(self._queue_name, message)
        queue_jobs_total.inc()
        return job_id

    async def dequeue(self, timeout: float = 1.0) -> tuple[str, str, dict[str, Any]] | None:
        await self.connect()
        result = await self._redis.blpop(self._queue_name, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        message = json.loads(raw)
        return message["job_id"], message["task"], message["payload"]

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


class InMemoryTaskQueue:
    """In-process queue for unit tests and local development without Redis."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, str, dict[str, Any]]] = asyncio.Queue()

    async def enqueue(self, task: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        await self._queue.put((job_id, task, payload))
        queue_jobs_total.inc()
        return job_id

    async def dequeue(self, timeout: float = 1.0) -> tuple[str, str, dict[str, Any]] | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def close(self) -> None:
        return None
