"""Task queue abstraction (spec §2.3, §23–§24, AT-023/024).

The queue is isolated behind a ``TaskQueue`` protocol so the implementation can
be replaced later (Celery/RQ/Arq) without touching producers or the worker
(ADR-005). Phase 0 ships a Redis-list-backed implementation and an in-memory
implementation for tests.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Protocol

from app.core.metrics import queue_jobs_total


class TaskQueue(Protocol):
    async def enqueue(self, task: str, payload: dict[str, Any], max_retries: int = 3) -> str: ...

    async def dequeue(self, timeout: float = 1.0) -> tuple[str, str, dict[str, Any]] | None: ...

    async def get_depth(self) -> int: ...

    async def get_dlq_depth(self) -> int: ...

    async def enqueue_dlq(self, job_id: str, task: str, payload: dict[str, Any], error: str) -> None: ...

    async def list_dlq(self, limit: int = 50) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...


class RedisTaskQueue:
    """Redis list-backed queue with Dead-Letter Queue (DLQ) support."""

    def __init__(self, redis_url: str, queue_name: str = "airex:queue") -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._dlq_name = f"{queue_name}:dlq"
        self._redis: Any = None

    async def connect(self) -> None:
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()

    async def enqueue(self, task: str, payload: dict[str, Any], max_retries: int = 3) -> str:
        await self.connect()
        job_id = str(uuid.uuid4())
        enriched_payload = dict(payload)
        enriched_payload.setdefault("_enqueued_at", time.time())
        enriched_payload.setdefault("_attempts", 0)
        enriched_payload.setdefault("_max_retries", max_retries)

        message = json.dumps({"job_id": job_id, "task": task, "payload": enriched_payload})
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

    async def get_depth(self) -> int:
        await self.connect()
        return await self._redis.llen(self._queue_name)

    async def get_dlq_depth(self) -> int:
        await self.connect()
        return await self._redis.llen(self._dlq_name)

    async def enqueue_dlq(self, job_id: str, task: str, payload: dict[str, Any], error: str) -> None:
        await self.connect()
        dlq_entry = json.dumps({
            "job_id": job_id,
            "task": task,
            "payload": payload,
            "error": error,
            "failed_at": time.time(),
        })
        await self._redis.rpush(self._dlq_name, dlq_entry)

    async def list_dlq(self, limit: int = 50) -> list[dict[str, Any]]:
        await self.connect()
        raw_items = await self._redis.lrange(self._dlq_name, -limit, -1)
        items = []
        for raw in raw_items:
            try:
                items.append(json.loads(raw))
            except Exception:
                continue
        return items

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


class InMemoryTaskQueue:
    """In-process queue with Dead-Letter Queue (DLQ) support for testing and local dev."""

    _shared_queue: asyncio.Queue[tuple[str, str, dict[str, Any]]] | None = None
    _shared_dlq: list[dict[str, Any]] | None = None

    @classmethod
    def reset(cls) -> None:
        cls._shared_queue = None
        cls._shared_dlq = None

    def __init__(self) -> None:
        if InMemoryTaskQueue._shared_queue is None:
            InMemoryTaskQueue._shared_queue = asyncio.Queue()
        if InMemoryTaskQueue._shared_dlq is None:
            InMemoryTaskQueue._shared_dlq = []
        self._queue = InMemoryTaskQueue._shared_queue
        self._dlq = InMemoryTaskQueue._shared_dlq

    async def enqueue(self, task: str, payload: dict[str, Any], max_retries: int = 3) -> str:
        job_id = str(uuid.uuid4())
        enriched_payload = dict(payload)
        enriched_payload.setdefault("_enqueued_at", time.time())
        enriched_payload.setdefault("_attempts", 0)
        enriched_payload.setdefault("_max_retries", max_retries)

        await self._queue.put((job_id, task, enriched_payload))
        queue_jobs_total.inc()
        return job_id

    async def dequeue(self, timeout: float = 1.0) -> tuple[str, str, dict[str, Any]] | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            return None

    async def get_depth(self) -> int:
        return self._queue.qsize()

    async def get_dlq_depth(self) -> int:
        return len(self._dlq)

    async def enqueue_dlq(self, job_id: str, task: str, payload: dict[str, Any], error: str) -> None:
        self._dlq.append({
            "job_id": job_id,
            "task": task,
            "payload": payload,
            "error": error,
            "failed_at": time.time(),
        })

    async def list_dlq(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._dlq[-limit:])

    async def close(self) -> None:
        return None
