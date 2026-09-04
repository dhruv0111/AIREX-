"""Unit tests for Phase 16 Worker Resilience, DLQ, Retries & Idempotency."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.workers.queue import InMemoryTaskQueue
from app.workers.worker import run_worker


@pytest.mark.asyncio
async def test_in_memory_queue_depth_and_dlq():
    queue = InMemoryTaskQueue()
    queue.reset()
    queue = InMemoryTaskQueue()

    assert await queue.get_depth() == 0
    assert await queue.get_dlq_depth() == 0

    # Enqueue tasks
    job1 = await queue.enqueue("test_task_1", {"foo": "bar"})
    job2 = await queue.enqueue("test_task_2", {"baz": "qux"})

    assert await queue.get_depth() == 2

    # Dequeue one
    item = await queue.dequeue(timeout=0.1)
    assert item is not None
    jid, tname, payload = item
    assert jid == job1
    assert tname == "test_task_1"
    assert "_enqueued_at" in payload
    assert "_attempts" in payload
    assert await queue.get_depth() == 1

    # Test DLQ
    await queue.enqueue_dlq(job1, "test_task_1", payload, "Fatal unrecoverable error")
    assert await queue.get_dlq_depth() == 1
    dlq_items = await queue.list_dlq(limit=10)
    assert len(dlq_items) == 1
    assert dlq_items[0]["job_id"] == job1
    assert dlq_items[0]["error"] == "Fatal unrecoverable error"


@pytest.mark.asyncio
async def test_worker_retry_exhaustion_moves_to_dlq():
    """Verify that a task failing multiple times exhausts retries and is moved to DLQ."""
    queue = InMemoryTaskQueue()
    queue.reset()
    queue = InMemoryTaskQueue()

    # Enqueue a task configured for max 2 retries
    job_id = await queue.enqueue("failing_task", {"param": "error_trigger"}, max_retries=2)

    # Register mock failing handler
    attempts_recorded = []

    async def mock_failing_handler(jid: str, payload: dict):
        attempts_recorded.append(payload.get("_attempts", 1))
        raise RuntimeError("Transient database lock timeout")

    with patch.dict("app.workers.worker.TASK_REGISTRY", {"failing_task": mock_failing_handler}):
        # Run worker with once=True on attempt 1
        await run_worker(once=True, poll_seconds=0.05)

        # Worker should have scheduled retry by re-enqueuing
        assert len(attempts_recorded) == 1
        assert await queue.get_depth() == 1

        # Run worker for attempt 2 (retry exhaustion)
        await run_worker(once=True, poll_seconds=0.05)

        assert len(attempts_recorded) == 2
        # After 2 attempts (max_retries=2), task is moved to DLQ and queue is empty
        assert await queue.get_depth() == 0
        assert await queue.get_dlq_depth() == 1
        dlq = await queue.list_dlq()
        assert "Exhausted 2 retries" in dlq[0]["error"]


@pytest.mark.asyncio
async def test_worker_task_idempotency():
    """Verify that duplicate tasks with the same idempotency key are skipped."""
    queue = InMemoryTaskQueue()
    queue.reset()
    queue = InMemoryTaskQueue()

    call_count = 0

    async def mock_success_handler(jid: str, payload: dict):
        nonlocal call_count
        call_count += 1
        return {"status": "ok"}

    # Enqueue two tasks with the SAME idempotency key
    await queue.enqueue("idempotent_task", {"idempotency_key": "unique_key_123", "val": 1})
    await queue.enqueue("idempotent_task", {"idempotency_key": "unique_key_123", "val": 2})

    with patch.dict("app.workers.worker.TASK_REGISTRY", {"idempotent_task": mock_success_handler}):
        # Run worker for both items
        await run_worker(once=True, poll_seconds=0.05)
        await run_worker(once=True, poll_seconds=0.05)

        # Only the first one should have executed!
        assert call_count == 1
