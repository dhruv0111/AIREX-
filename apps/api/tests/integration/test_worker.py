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


@pytest.mark.asyncio
async def test_worker_graceful_shutdown_and_concurrency(session_factory, monkeypatch):
    import asyncio
    from app.workers.worker import run_worker
    from app.workers.queue import InMemoryTaskQueue

    monkeypatch.setattr("app.workers.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    queue = InMemoryTaskQueue()

    started_tasks = []
    completed_tasks = []

    async def slow_test_task(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        started_tasks.append(job_id)
        await asyncio.sleep(0.2)
        completed_tasks.append(job_id)
        return {"status": "done"}

    TASK_REGISTRY["slow_test_task"] = slow_test_task

    try:
        for i in range(3):
            await queue.enqueue("slow_test_task", {"task_index": i})

        worker_task = asyncio.create_task(run_worker(once=False, poll_seconds=0.01))
        
        # Wait up to 1.0s for the 3 tasks to be dequeued and started
        for _ in range(20):
            if len(started_tasks) == 3:
                break
            await asyncio.sleep(0.05)

        assert len(started_tasks) == 3
        assert len(completed_tasks) == 0

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        assert len(completed_tasks) == 3
    finally:
        del TASK_REGISTRY["slow_test_task"]
        await queue.close()


@pytest.mark.asyncio
async def test_worker_task_failure_isolation(session_factory, monkeypatch):
    import asyncio
    from app.workers.worker import run_worker
    from app.workers.queue import InMemoryTaskQueue

    monkeypatch.setattr("app.workers.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    queue = InMemoryTaskQueue()

    failing_started = asyncio.Event()
    success_completed = asyncio.Event()

    async def failing_task(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        failing_started.set()
        raise RuntimeError("simulated task failure")

    async def success_task(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        success_completed.set()
        return {"status": "ok"}

    TASK_REGISTRY["failing_task"] = failing_task
    TASK_REGISTRY["success_task"] = success_task

    try:
        await queue.enqueue("failing_task", {})
        await queue.enqueue("success_task", {})

        worker_task = asyncio.create_task(run_worker(once=False, poll_seconds=0.01))

        try:
            await asyncio.wait_for(success_completed.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass

        assert failing_started.is_set()
        assert success_completed.is_set()

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    finally:
        del TASK_REGISTRY["failing_task"]
        del TASK_REGISTRY["success_task"]
        await queue.close()
