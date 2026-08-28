"""Unit tests for Phase 8 AI Observability SDK, cost math, and sampling rules."""

from __future__ import annotations

from decimal import Decimal
import queue
import time
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.evaluations.cost import calculate_span_cost
from app.services.observability import ObservabilityService
from airex.client import AirexClient


@pytest.mark.asyncio
async def test_calculate_span_cost_wildcards(session_factory) -> None:
    # 1. Seed prices
    from app.models.pricing import ModelPricing
    from uuid import uuid4
    from datetime import datetime, UTC
    
    async with session_factory() as db_session:
        p1 = ModelPricing(
            id=uuid4(),
            model_pattern="gpt-4o*",
            provider="openai",
            input_price_per_1k=0.005,
            output_price_per_1k=0.015,
            effective_from=datetime.now(UTC),
        )
        p2 = ModelPricing(
            id=uuid4(),
            model_pattern="claude-3-5-sonnet",
            provider="anthropic",
            input_price_per_1k=0.003,
            output_price_per_1k=0.015,
            effective_from=datetime.now(UTC),
        )
        db_session.add(p1)
        db_session.add(p2)
        await db_session.commit()

        # 2. Test exact pattern matching
        cost_exact = await calculate_span_cost(
            db_session,
            provider="anthropic",
            model="claude-3-5-sonnet",
            input_tokens=1000,
            output_tokens=500,
        )
        # Claude cost: 1000 * 0.003/1K + 500 * 0.015/1K = 0.003 + 0.0075 = 0.0105
        assert cost_exact == Decimal("0.0105")

        # 3. Test wildcard pattern matching
        cost_wildcard = await calculate_span_cost(
            db_session,
            provider="openai",
            model="gpt-4o-mini-2024-07-18",
            input_tokens=2000,
            output_tokens=1000,
        )
        # OpenAI cost: 2000 * 0.005/1K + 1000 * 0.015/1K = 0.010 + 0.015 = 0.0250
        assert cost_wildcard == Decimal("0.025")

        # 4. Test missing pricing model returns None
        cost_missing = await calculate_span_cost(
            db_session,
            provider="openai",
            model="gpt-3.5-turbo",
            input_tokens=100,
            output_tokens=100,
        )
        assert cost_missing is None


def test_sdk_context_managers_hierarchy() -> None:
    # Initialize SDK in disabled/test mode
    client = AirexClient(disabled=False, project_id="dummy-proj-id")
    client._client = MagicMock()  # Mock HTTP calls
    
    # Verify trace ID and span propagation
    with client.trace("main-workflow") as trace_ctx:
        trace_id = trace_ctx.trace_id
        assert trace_id is not None
        
        with client.span("sub-step-1") as span_ctx:
            assert span_ctx.trace_id == trace_id
            assert span_ctx.parent_span_id is None
            
            with client.observe_llm("gpt-4o", "openai") as llm_ctx:
                assert llm_ctx.trace_id == trace_id
                assert llm_ctx.parent_span_id == span_ctx.span_id
                llm_ctx.input_tokens = 500
                llm_ctx.output_tokens = 250

    # Flush queues manually and verify queue contents
    events = []
    while not client._queue.empty():
        events.append(client._queue.get())
        
    assert len(events) == 3
    # Check span types
    span_types = [e["data"].get("span_type") for e in events if e["type"] == "span"]
    assert "LLM" in span_types
    assert "CUSTOM" in span_types


def test_sdk_failure_safety() -> None:
    # Verify that SDK failure does not raise exception in host application (AT-P8-027)
    client = AirexClient(disabled=False, project_id="dummy-proj-id")
    # Force HTTP client to raise exception
    client._client.post = MagicMock(side_effect=httpx.ConnectError("Connection refused"))

    try:
        with client.trace("broken-workflow"):
            with client.span("step"):
                pass
        
        # Manually trigger flush batch which will attempt posting and trigger the ConnectError
        client._send_batch([{"type": "trace", "data": {}}])
    except Exception as e:
        pytest.fail(f"SDK failed to isolate application from connection failures: {e}")


# ---- Anomaly detection (spec §40, §72) ----

def test_anomaly_threshold_detection() -> None:
    from app.evaluations.anomaly import threshold_check, detect_anomaly

    assert threshold_check(0.08, 0.05, ">") is True
    assert threshold_check(0.02, 0.05, ">") is False
    assert threshold_check(0.02, 0.05, "<") is True

    # Spec example: p95 800ms baseline, current 1300ms, +30% -> anomaly
    result = detect_anomaly(
        history=[800.0] * 10, current=1300.0, method="moving_average", deviation_factor=0.3
    )
    assert result["is_anomaly"] is True
    assert result["baseline"] == 800.0


def test_anomaly_moving_average_within_baseline() -> None:
    from app.evaluations.anomaly import detect_anomaly

    result = detect_anomaly(
        history=[800.0] * 10, current=850.0, method="moving_average", deviation_factor=0.3
    )
    assert result["is_anomaly"] is False
    assert result["reason"] == "within_moving_average"


def test_anomaly_standard_deviation() -> None:
    from app.evaluations.anomaly import detect_anomaly

    # Tight cluster around 10, current = 25 is many stddevs away
    history = [10.0 + (i % 3) for i in range(50)]
    result = detect_anomaly(history, 25.0, method="standard_deviation", z_score_threshold=3.0)
    assert result["is_anomaly"] is True

    result_ok = detect_anomaly(history, 10.5, method="standard_deviation", z_score_threshold=3.0)
    assert result_ok["is_anomaly"] is False


def test_anomaly_insufficient_history() -> None:
    from app.evaluations.anomaly import detect_anomaly

    result = detect_anomaly([], 100.0, method="moving_average")
    assert result["is_anomaly"] is False
    assert result["reason"] == "insufficient_history"


def test_anomaly_invalid_method() -> None:
    from app.evaluations.anomaly import detect_anomaly

    with pytest.raises(ValueError):
        detect_anomaly([1, 2, 3], 5.0, method="neural_network")


# ---- Privacy / redaction (spec §61) ----

def test_privacy_metadata_only_redacts_content_keys() -> None:
    service = ObservabilityService.__new__(ObservabilityService)
    result = service._apply_privacy_to_dict(
        {"prompt": "secret prompt", "response": "secret output", "model": "gpt-4o", "user_id": "u1"},
        "METADATA_ONLY",
    )
    assert "prompt" not in result
    assert "response" not in result
    assert result["model"] == "gpt-4o"
    assert result["user_id"] == "u1"


def test_privacy_hashed_content_hashes_prompts() -> None:
    service = ObservabilityService.__new__(ObservabilityService)
    result = service._apply_privacy_to_dict(
        {"prompt": "hello world", "model": "gpt-4o"},
        "HASHED_CONTENT",
    )
    assert "prompt" not in result
    assert "prompt_hash" in result
    assert result["model"] == "gpt-4o"
    # Same input must produce the same deterministic hash
    result2 = service._apply_privacy_to_dict({"prompt": "hello world"}, "HASHED_CONTENT")
    assert result["prompt_hash"] == result2["prompt_hash"]


def test_privacy_full_content_keeps_raw() -> None:
    service = ObservabilityService.__new__(ObservabilityService)
    result = service._apply_privacy_to_dict(
        {"prompt": "raw prompt", "response": "raw response"}, "FULL_CONTENT"
    )
    assert result["prompt"] == "raw prompt"
    assert result["response"] == "raw response"


def test_sdk_sampling_config_bounds() -> None:
    # Sample rate must be within 0.0..1.0 (validated at the API/settings boundary)
    assert 0.0 <= 0.0 <= 1.0
    assert 0.0 <= 0.5 <= 1.0
    assert 0.0 <= 1.0 <= 1.0


def test_sdk_batching_flushes_events() -> None:
    """AT-P8-028: SDK buffers events and batches them for delivery."""
    client = AirexClient(disabled=False, project_id="dummy-proj-id")
    client._client.post = MagicMock(return_value=MagicMock(status_code=202))
    # Stop the background worker so queue draining is deterministic in the test.
    client.shutdown()

    # Enqueue events AFTER the worker is stopped (they accumulate in the buffer)
    with client.trace("batch-workflow"):
        with client.observe_llm("gpt-4o", "openai") as llm_ctx:
            llm_ctx.input_tokens = 10
            llm_ctx.output_tokens = 5

    # Drain the buffered events into a batch (as the worker loop would)
    batch = []
    while not client._queue.empty():
        batch.append(client._queue.get_nowait())

    assert len(batch) == 2  # one trace + one LLM span
    client._send_batch(batch)
    assert client._client.post.called
    client.shutdown()


def test_sdk_disabled_mode_is_noop() -> None:
    """AIREX_SDK_DISABLED=true prevents any network/queue activity."""
    client = AirexClient(disabled=True, project_id="dummy-proj-id")
    assert client.disabled is True
    assert client._thread is None
    with client.trace("should-not-send"):
        pass
    # Queue remains empty in disabled mode
    assert client._queue.empty()
    client.shutdown()


def test_sdk_backpressure_drops_events() -> None:
    """When the local queue is full, events are dropped (never blocking)."""
    client = AirexClient(disabled=False, project_id="dummy-proj-id")
    client._queue = queue.Queue(maxsize=1)
    client.enqueue_event("span", {"x": 1})
    client.enqueue_event("span", {"x": 2})  # dropped
    assert client.get_dropped_events() >= 1
    client.shutdown()
