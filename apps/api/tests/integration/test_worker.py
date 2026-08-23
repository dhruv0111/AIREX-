"""Worker/queue tests (AT-023/024)."""

from __future__ import annotations

import pytest

from app.workers.queue import InMemoryTaskQueue
from app.workers.tasks import TASK_REGISTRY


@pytest.mark.asyncio
async def test_at024_in_memory_queue_receive_execute_complete():
    queue = InMemoryTaskQueue()
    job_id = await queue.enqueue("test_job", {"hello": "world"})
    item = await queue.dequeue(timeout=0.1)
    assert item is not None
    got_job_id, task, payload = item
    assert got_job_id == job_id
    assert task == "test_job"

    result = await TASK_REGISTRY["test_job"](got_job_id, payload)
    assert result["status"] == "completed"
    await queue.close()


@pytest.mark.asyncio
async def test_queue_empty_returns_none():
    queue = InMemoryTaskQueue()
    assert await queue.dequeue(timeout=0.05) is None
    await queue.close()


@pytest.mark.asyncio
async def test_unknown_task_registry_lookup():
    assert "no_such_task" not in TASK_REGISTRY
