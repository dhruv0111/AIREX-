"""Model Gateway tests (spec §14–§16, §55; AT-P1-010..013)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.errors import ValidationFailure
from app.integrations.gateway import ModelGatewayService
from app.integrations.provider import (
    ErrorCategory,
    ModelRequest,
    ProviderError,
    RetryPolicy,
)
from app.schemas.provider import ModelInvokeRequest


@pytest.mark.asyncio
async def test_gateway_local_invoke_normalized():
    gateway = ModelGatewayService()
    response = await gateway.invoke(
        provider_type="LOCAL",
        api_key=None,
        base_url=None,
        configuration={"latency_ms": 10},
        request=ModelRequest(model="local-test", messages=[{"role": "user", "content": "Hi"}]),
        retry_policy=RetryPolicy(max_retries=0),
    )
    assert response.provider == "LOCAL"
    assert response.usage.total_tokens > 0
    assert response.latency_ms >= 10


@pytest.mark.asyncio
async def test_gateway_retries_transient_then_succeeds(monkeypatch):
    # Local provider fails once with rate_limit then (config changed) succeeds.
    gateway = ModelGatewayService()

    class FlakyAdapter:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        async def invoke(self, request):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "first fail")
            return type(
                "R",
                (),
                {
                    "id": "x",
                    "provider": "LOCAL",
                    "model": request.model,
                    "content": "ok",
                    "finish_reason": "stop",
                    "usage": type(
                        "U", (), {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
                    )(),
                    "latency_ms": 1,
                    "metadata": {},
                    "created_at": "now",
                },
            )()

    import app.integrations.gateway as gateway_module

    flaky = FlakyAdapter()
    monkeypatch.setattr(gateway_module, "build_adapter", lambda *a, **k: flaky)
    response = await gateway.invoke(
        provider_type="LOCAL",
        api_key=None,
        base_url=None,
        configuration={},
        request=ModelRequest(model="m", messages=[{"role": "user", "content": "x"}]),
        retry_policy=RetryPolicy(max_retries=2, initial_delay_ms=1),
    )
    assert response.content == "ok"
    assert flaky.calls == 2


@pytest.mark.asyncio
async def test_gateway_no_retry_for_permanent():
    gateway = ModelGatewayService()
    with pytest.raises(ProviderError) as exc_info:
        await gateway.invoke(
            provider_type="LOCAL",
            api_key=None,
            base_url=None,
            configuration={"failure_mode": "invalid_request"},
            request=ModelRequest(model="m", messages=[{"role": "user", "content": "x"}]),
            retry_policy=RetryPolicy(max_retries=5, initial_delay_ms=1),
        )
    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST_ERROR


@pytest.mark.asyncio
async def test_gateway_retry_exhausts_then_raises(monkeypatch):
    """Transient error with max_retries=2 → exactly 3 attempts, then raises."""
    import app.integrations.gateway as gateway_module

    class AlwaysTransient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        async def invoke(self, request):
            self.calls += 1
            raise ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "still limited")

    adapter = AlwaysTransient()
    monkeypatch.setattr(gateway_module, "build_adapter", lambda *a, **k: adapter)

    gateway = ModelGatewayService()
    with pytest.raises(ProviderError):
        await gateway.invoke(
            provider_type="LOCAL",
            api_key=None,
            base_url=None,
            configuration={},
            request=ModelRequest(model="m", messages=[{"role": "user", "content": "x"}]),
            retry_policy=RetryPolicy(max_retries=2, initial_delay_ms=1, max_delay_ms=5),
        )
    assert adapter.calls == 3  # attempt 1 + 2 retries (no attempt 4)


def test_invocation_validation_max_tokens():
    gateway = ModelGatewayService()
    with pytest.raises(ValidationFailure):
        gateway.validate_invocation(max_tokens=0, temperature=None)
    with pytest.raises(ValidationFailure):
        gateway.validate_invocation(max_tokens=1000000, temperature=None)


def test_invocation_validation_temperature():
    gateway = ModelGatewayService()
    with pytest.raises(ValidationFailure):
        gateway.validate_invocation(max_tokens=None, temperature=-1)
    with pytest.raises(ValidationFailure):
        gateway.validate_invocation(max_tokens=None, temperature=3.0)
    gateway.validate_invocation(max_tokens=100, temperature=1.5)  # ok


def test_schema_validates_invoke_request():
    # max_tokens <= 0 rejected at the schema level (spec §55).
    with pytest.raises(ValidationError):
        ModelInvokeRequest(messages=[{"role": "user", "content": "x"}], max_tokens=0)
    with pytest.raises(ValidationError):
        ModelInvokeRequest(messages=[{"role": "user", "content": "x"}], temperature=-0.5)
