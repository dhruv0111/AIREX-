"""Provider adapter unit tests (spec §57).

Local provider is deterministic; OpenAI/Anthropic/Gemini adapters are tested
with a mocked HTTP transport — no paid external API is ever called.
"""

from __future__ import annotations

import httpx
import pytest

from app.integrations.provider import (
    ErrorCategory,
    LocalProviderAdapter,
    ModelRequest,
    OpenAIProviderAdapter,
    ProviderError,
)


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict) -> None:
        self.status_code = status_code
        self._body = json_body

    def json(self) -> dict:
        return self._body


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.last_url = None
        self.last_headers = None
        self.last_json = None
        self.last_params = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url: str, headers=None, json=None, **kwargs):
        self.last_url = url
        self.last_headers = headers
        self.last_json = json
        self.last_params = kwargs.get("params")
        return self._response


def _request(**overrides) -> ModelRequest:
    defaults = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]}
    defaults.update(overrides)
    return ModelRequest(**defaults)


def _install_fake(monkeypatch, response: FakeResponse) -> FakeClient:
    client = FakeClient(response)

    def _fake_factory(*args, **kwargs) -> FakeClient:
        return client

    monkeypatch.setattr(httpx, "AsyncClient", _fake_factory)
    return client


# ---------------------------------------------------------------------------
# Local provider
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_local_provider_success():
    adapter = LocalProviderAdapter({"latency_ms": 0})
    resp = await adapter.invoke(_request())
    assert resp.provider == "LOCAL"
    assert resp.usage.total_tokens > 0
    assert resp.finish_reason == "stop"
    assert resp.metadata["deterministic"] is True


@pytest.mark.asyncio
async def test_local_provider_failure_modes():
    cases = {
        "rate_limit": ErrorCategory.RATE_LIMIT_ERROR,
        "auth": ErrorCategory.AUTHENTICATION_ERROR,
        "timeout": ErrorCategory.TIMEOUT_ERROR,
        "unavailable": ErrorCategory.PROVIDER_UNAVAILABLE,
        "invalid_request": ErrorCategory.INVALID_REQUEST_ERROR,
    }
    for mode, category in cases.items():
        adapter = LocalProviderAdapter({"failure_mode": mode})
        with pytest.raises(ProviderError) as exc_info:
            await adapter.invoke(_request())
        assert exc_info.value.category == category


@pytest.mark.asyncio
async def test_local_provider_simulated_latency():
    adapter = LocalProviderAdapter({"latency_ms": 30})
    resp = await adapter.invoke(_request())
    assert resp.latency_ms >= 30


# ---------------------------------------------------------------------------
# OpenAI adapter (mocked transport)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_openai_success_and_usage(monkeypatch):
    body = {
        "id": "chatcmpl_123",
        "model": "gpt-test",
        "choices": [{"message": {"content": "Hello there"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 9, "total_tokens": 19},
    }
    client = _install_fake(monkeypatch, FakeResponse(200, body))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    resp = await adapter.invoke(_request())
    assert resp.content == "Hello there"
    assert resp.provider == "OPENAI"
    assert resp.usage.total_tokens == 19
    assert resp.latency_ms >= 0
    assert "Authorization" in client.last_headers


@pytest.mark.asyncio
async def test_openai_authentication_error(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(401, {"error": {"message": "bad key"}}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.AUTHENTICATION_ERROR
    assert "sk-test" not in exc_info.value.message


@pytest.mark.asyncio
async def test_openai_rate_limit(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(429, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.RATE_LIMIT_ERROR
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_openai_model_not_found(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(404, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.MODEL_NOT_FOUND
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_openai_missing_key(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(200, {}))
    adapter = OpenAIProviderAdapter({})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.AUTHENTICATION_ERROR


@pytest.mark.asyncio
async def test_openai_invalid_request(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(400, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST_ERROR
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_openai_provider_unavailable(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(503, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_openai_validate_configuration_requires_key():
    adapter = OpenAIProviderAdapter({})
    with pytest.raises(ProviderError):
        await adapter.validate_configuration({})


# ---------------------------------------------------------------------------
# Anthropic adapter (mocked transport)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_anthropic_success_and_usage(monkeypatch):
    body = {
        "id": "msg_123",
        "model": "claude-test",
        "content": [{"type": "text", "text": "Hello there"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 12, "output_tokens": 8},
    }
    client = _install_fake(monkeypatch, FakeResponse(200, body))
    from app.integrations.provider import AnthropicProviderAdapter

    adapter = AnthropicProviderAdapter({"api_key": "ant-test"})
    resp = await adapter.invoke(_request())
    assert resp.content == "Hello there"
    assert resp.provider == "ANTHROPIC"
    assert resp.usage.total_tokens == 20
    assert client.last_headers.get("x-api-key") == "ant-test"


# ---------------------------------------------------------------------------
# Gemini adapter (mocked transport)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gemini_success_and_usage(monkeypatch):
    body = {
        "candidates": [{"content": {"parts": [{"text": "Hello there"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 5},
    }
    client = _install_fake(monkeypatch, FakeResponse(200, body))
    from app.integrations.provider import GeminiProviderAdapter

    adapter = GeminiProviderAdapter({"api_key": "g-key"})
    resp = await adapter.invoke(_request())
    assert resp.content == "Hello there"
    assert resp.provider == "GOOGLE"
    assert resp.usage.total_tokens == 12
    assert client.last_params == {"key": "g-key"}


# ---------------------------------------------------------------------------
# Error normalization matrix (spec §9; AT-P1-013 etc.)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_openai_authorization_error_403(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(403, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.AUTHORIZATION_ERROR
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_openai_provider_unavailable_500(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(500, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_openai_unknown_status(monkeypatch):
    _install_fake(monkeypatch, FakeResponse(418, {}))
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.UNKNOWN_PROVIDER_ERROR


@pytest.mark.asyncio
async def test_openai_timeout_normalized(monkeypatch):
    from app.integrations.provider import OpenAIProviderAdapter

    async def _raise_timeout(url, headers=None, json=None, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    client = FakeClient(FakeResponse(200, {}))
    client.post = _raise_timeout
    _install_fake(monkeypatch, FakeResponse(200, {}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: client)
    adapter = OpenAIProviderAdapter({"api_key": "sk-test"})
    with pytest.raises(ProviderError) as exc_info:
        await adapter.invoke(_request())
    assert exc_info.value.category == ErrorCategory.TIMEOUT_ERROR


@pytest.mark.asyncio
async def test_openai_health_check_degraded(monkeypatch):
    # Missing key makes validate_configuration fail → health is degraded.
    adapter = OpenAIProviderAdapter({})
    health = await adapter.health_check()
    assert health.status == "degraded"
    assert health.error is not None


@pytest.mark.asyncio
async def test_anthropic_error_matrix(monkeypatch):
    from app.integrations.provider import AnthropicProviderAdapter

    cases = {
        401: ErrorCategory.AUTHENTICATION_ERROR,
        403: ErrorCategory.AUTHORIZATION_ERROR,
        429: ErrorCategory.RATE_LIMIT_ERROR,
        400: ErrorCategory.INVALID_REQUEST_ERROR,
        404: ErrorCategory.MODEL_NOT_FOUND,
        503: ErrorCategory.PROVIDER_UNAVAILABLE,
    }
    for status, category in cases.items():
        _install_fake(monkeypatch, FakeResponse(status, {}))
        adapter = AnthropicProviderAdapter({"api_key": "ant-test"})
        with pytest.raises(ProviderError) as exc_info:
            await adapter.invoke(_request())
        assert exc_info.value.category == category, f"status {status}"


@pytest.mark.asyncio
async def test_anthropic_validate_configuration_requires_key():
    from app.integrations.provider import AnthropicProviderAdapter

    adapter = AnthropicProviderAdapter({})
    with pytest.raises(ProviderError):
        await adapter.validate_configuration({})


@pytest.mark.asyncio
async def test_anthropic_health_check_degraded(monkeypatch):
    from app.integrations.provider import AnthropicProviderAdapter

    adapter = AnthropicProviderAdapter({})
    health = await adapter.health_check()
    assert health.status == "degraded"


@pytest.mark.asyncio
async def test_gemini_error_matrix(monkeypatch):
    from app.integrations.provider import GeminiProviderAdapter

    cases = {
        401: ErrorCategory.AUTHENTICATION_ERROR,
        403: ErrorCategory.AUTHORIZATION_ERROR,
        429: ErrorCategory.RATE_LIMIT_ERROR,
        400: ErrorCategory.INVALID_REQUEST_ERROR,
        404: ErrorCategory.MODEL_NOT_FOUND,
        503: ErrorCategory.PROVIDER_UNAVAILABLE,
    }
    for status, category in cases.items():
        _install_fake(monkeypatch, FakeResponse(status, {}))
        adapter = GeminiProviderAdapter({"api_key": "g-key"})
        with pytest.raises(ProviderError) as exc_info:
            await adapter.invoke(_request())
        assert exc_info.value.category == category, f"status {status}"


@pytest.mark.asyncio
async def test_gemini_validate_configuration_requires_key():
    from app.integrations.provider import GeminiProviderAdapter

    adapter = GeminiProviderAdapter({})
    with pytest.raises(ProviderError):
        await adapter.validate_configuration({})


@pytest.mark.asyncio
async def test_gemini_health_check_degraded(monkeypatch):
    from app.integrations.provider import GeminiProviderAdapter

    adapter = GeminiProviderAdapter({})
    health = await adapter.health_check()
    assert health.status == "degraded"


@pytest.mark.asyncio
async def test_local_health_check_failure_modes():
    # Health checks surface unavailable/timeout failures; other failure modes
    # still raise on invoke but the health endpoint reports healthy.
    for mode in ("unavailable", "timeout"):
        adapter = LocalProviderAdapter({"failure_mode": mode})
        health = await adapter.health_check()
        assert health.status == "unavailable"
        assert health.error == mode
    for mode in ("rate_limit", "auth", "invalid_request"):
        adapter = LocalProviderAdapter({"failure_mode": mode})
        health = await adapter.health_check()
        assert health.status == "healthy"


@pytest.mark.asyncio
async def test_local_health_check_healthy():
    adapter = LocalProviderAdapter({})
    health = await adapter.health_check("m")
    assert health.status == "healthy"
    assert health.model == "m"


def test_build_adapter_unknown_type():
    from app.integrations.provider import build_adapter

    with pytest.raises(ProviderError) as exc_info:
        build_adapter("BOGUS", {})
    assert exc_info.value.category == ErrorCategory.INVALID_REQUEST_ERROR


def test_build_adapter_registry():
    from app.integrations.provider import (
        AnthropicProviderAdapter,
        GeminiProviderAdapter,
        LocalProviderAdapter,
        OpenAIProviderAdapter,
        build_adapter,
    )

    assert isinstance(build_adapter("LOCAL", {}), LocalProviderAdapter)
    assert isinstance(build_adapter("OPENAI", {}), OpenAIProviderAdapter)
    assert isinstance(build_adapter("ANTHROPIC", {}), AnthropicProviderAdapter)
    assert isinstance(build_adapter("GOOGLE", {}), GeminiProviderAdapter)
    assert isinstance(build_adapter("CUSTOM", {}), GeminiProviderAdapter)
