"""Model Gateway provider abstraction (spec §5–§16; ADR-009/011).

Business logic never depends on a specific AI provider. Every provider call
flows through the neutral ``ModelGateway`` interface and the normalized
``ModelRequest``/``ModelResponse`` models. Adapters: LOCAL (deterministic,
offline), OPENAI, ANTHROPIC, GOOGLE (real HTTP adapters; never called in tests
— tests mock the HTTP transport or use the local provider).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.ssrf import validate_base_url

logger = get_logger("gateway")


# ---------------------------------------------------------------------------
# Enums & data models
# ---------------------------------------------------------------------------
class ProviderType(StrEnum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE = "GOOGLE"
    CUSTOM = "CUSTOM"
    LOCAL = "LOCAL"


class ErrorCategory(StrEnum):
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    INVALID_REQUEST_ERROR = "INVALID_REQUEST_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


_TRANSIENT = {
    ErrorCategory.TIMEOUT_ERROR,
    ErrorCategory.RATE_LIMIT_ERROR,
    ErrorCategory.PROVIDER_UNAVAILABLE,
}


class ProviderError(AppError):
    """Normalized provider error surfaced through the standard envelope."""

    _STATUS = {
        ErrorCategory.AUTHENTICATION_ERROR: 401,
        ErrorCategory.AUTHORIZATION_ERROR: 403,
        ErrorCategory.RATE_LIMIT_ERROR: 429,
        ErrorCategory.TIMEOUT_ERROR: 504,
        ErrorCategory.INVALID_REQUEST_ERROR: 400,
        ErrorCategory.MODEL_NOT_FOUND: 404,
        ErrorCategory.PROVIDER_UNAVAILABLE: 503,
        ErrorCategory.PROVIDER_ERROR: 502,
        ErrorCategory.UNKNOWN_PROVIDER_ERROR: 502,
    }

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.category = category
        self.status_code = self._STATUS[category]
        self.code = category.value
        self.retryable = retryable if retryable is not None else category in _TRANSIENT


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ModelRequest:
    model: str
    messages: list[dict[str, str]]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    timeout: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)
    stream: bool = False


@dataclass
class ModelResponse:
    id: str
    provider: str
    model: str
    content: str
    finish_reason: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ProviderHealth:
    status: str  # healthy | degraded | unavailable | unknown
    provider: str
    model: str = ""
    last_checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    latency_ms: int = 0
    error: str | None = None


@dataclass
class RetryPolicy:
    max_retries: int = 3
    initial_delay_ms: int = 250
    max_delay_ms: int = 5000
    backoff_multiplier: float = 2.0


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------
class ProviderAdapter(Protocol):
    provider_type: ProviderType

    async def invoke(self, request: ModelRequest) -> ModelResponse: ...

    async def health_check(self, model: str | None = None) -> ProviderHealth: ...

    async def validate_configuration(self, config: dict[str, Any]) -> None: ...


def get_api_key(provider: str, config: dict[str, Any]) -> str:
    key = config.get("api_key", "")
    if not key:
        raise ProviderError(
            ErrorCategory.AUTHENTICATION_ERROR,
            "Provider credentials are not configured.",
        )
    return key


# ---------------------------------------------------------------------------
# Retry with exponential backoff (spec §15)
# ---------------------------------------------------------------------------
async def run_with_retry(
    operation: Any,
    policy: RetryPolicy,
    *,
    timeout: float,
) -> Any:
    """Run an async provider operation with exponential backoff on transient errors."""
    attempt = 0
    delay_ms: float = policy.initial_delay_ms
    while True:
        try:
            return await asyncio.wait_for(operation(), timeout=timeout)
        except ProviderError as exc:
            if not exc.retryable or attempt >= policy.max_retries:
                raise
            attempt += 1
            logger.warning(
                "provider retry",
                extra={
                    "attempt": attempt,
                    "max": policy.max_retries,
                    "category": exc.category.value,
                },
            )
            await asyncio.sleep(delay_ms / 1000.0)
            delay_ms = min(delay_ms * policy.backoff_multiplier, policy.max_delay_ms)
        except (httpx.TimeoutException, TimeoutError):
            if attempt >= policy.max_retries:
                raise ProviderError(ErrorCategory.TIMEOUT_ERROR, "The provider timed out.")
            attempt += 1
            await asyncio.sleep(delay_ms / 1000.0)
            delay_ms = min(delay_ms * policy.backoff_multiplier, policy.max_delay_ms)


# ---------------------------------------------------------------------------
# Local provider (deterministic, offline) — spec §13
# ---------------------------------------------------------------------------
class LocalProviderAdapter:
    """Deterministic provider used for tests and local development.

    Configuration: {"failure_mode": "rate_limit"|"auth"|"timeout"|null,
                    "latency_ms": 50, "local_content": "..."}

    ``local_content`` (Phase 4) lets tests configure a deterministic structured
    response (e.g. valid judge JSON) so the suite never needs real LLM keys.
    """

    provider_type = ProviderType.LOCAL

    def __init__(
        self, config: dict[str, Any] | None = None, settings: Settings | None = None
    ) -> None:
        self._config = config or {}
        self._settings = settings or get_settings()

    def _failure_mode(self) -> str | None:
        return self._config.get("failure_mode")

    async def _simulate_latency(self) -> None:
        latency = int(self._config.get("latency_ms", 0) or 0)
        if latency > 0:
            await asyncio.sleep(latency / 1000.0)

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        await self._simulate_latency()
        mode = self._failure_mode()
        if mode == "rate_limit":
            raise ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "Simulated provider rate limit.")
        if mode == "auth":
            raise ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "Simulated authentication failure."
            )
        if mode == "timeout":
            raise ProviderError(ErrorCategory.TIMEOUT_ERROR, "Simulated provider timeout.")
        if mode == "unavailable":
            raise ProviderError(
                ErrorCategory.PROVIDER_UNAVAILABLE, "Simulated provider unavailable."
            )
        if mode == "invalid_request":
            raise ProviderError(ErrorCategory.INVALID_REQUEST_ERROR, "Simulated invalid request.")

        last_user = next(
            (m["content"] for m in reversed(request.messages) if m.get("role") == "user"), ""
        )
        if self._config.get("local_content"):
            # Deterministic override (mocked judge/structured responses).
            content = str(self._config["local_content"])
        else:
            content = f"[local:{request.model}] {last_user[:200]}"
        input_tokens = max(1, len(last_user) // 4)
        output_tokens = max(1, len(content) // 4)
        return ModelResponse(
            id=f"local_{uuid.uuid4().hex[:12]}",
            provider=ProviderType.LOCAL.value,
            model=request.model,
            content=content,
            finish_reason="stop",
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            latency_ms=int(self._config.get("latency_ms", 0) or 0),
            metadata={"provider": "local", "paid_provider": False, "deterministic": True},
        )

    async def health_check(self, model: str | None = None) -> ProviderHealth:
        await self._simulate_latency()
        mode = self._failure_mode()
        if mode in ("unavailable", "timeout"):
            return ProviderHealth(
                status="unavailable",
                provider=ProviderType.LOCAL.value,
                error=mode,
            )
        return ProviderHealth(
            status="healthy", provider=ProviderType.LOCAL.value, model=model or ""
        )

    async def validate_configuration(self, config: dict[str, Any]) -> None:
        # LOCAL accepts a minimal, documented configuration only.
        return None


# ---------------------------------------------------------------------------
# OpenAI adapter (OpenAI-compatible /chat/completions) — spec §10
# ---------------------------------------------------------------------------
class OpenAIProviderAdapter:
    provider_type = ProviderType.OPENAI

    def __init__(
        self, config: dict[str, Any] | None = None, settings: Settings | None = None
    ) -> None:
        self._config = config or {}
        self._settings = settings or get_settings()

    def _base_url(self) -> str:
        return validate_base_url(
            self._config.get("base_url") or "https://api.openai.com/v1",
            allow_local=self._settings.is_development,
        )

    async def validate_configuration(self, config: dict[str, Any]) -> None:
        if not config.get("api_key"):
            raise ProviderError(ErrorCategory.AUTHENTICATION_ERROR, "OpenAI API key is required.")
        validate_base_url(
            config.get("base_url") or "https://api.openai.com/v1",
            allow_local=self._settings.is_development,
        )

    def _normalize_error(self, exc: Exception | None, status: int | None = None) -> ProviderError:
        if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            return ProviderError(ErrorCategory.TIMEOUT_ERROR, "The OpenAI provider timed out.")
        if status == 401:
            return ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "OpenAI authentication failed."
            )
        if status == 403:
            return ProviderError(ErrorCategory.AUTHORIZATION_ERROR, "OpenAI authorization failed.")
        if status == 429:
            return ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "OpenAI rate limit exceeded.")
        if status == 400:
            return ProviderError(ErrorCategory.INVALID_REQUEST_ERROR, "Invalid request to OpenAI.")
        if status == 404:
            return ProviderError(ErrorCategory.MODEL_NOT_FOUND, "OpenAI model not found.")
        if status and status >= 500:
            return ProviderError(ErrorCategory.PROVIDER_UNAVAILABLE, "OpenAI is unavailable.")
        return ProviderError(ErrorCategory.UNKNOWN_PROVIDER_ERROR, "Unknown OpenAI error.")

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        key = get_api_key(self.provider_type.value, self._config)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            body["top_p"] = request.top_p

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=request.timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url()}/chat/completions", headers=headers, json=body
                )
            except Exception as exc:
                raise self._normalize_error(exc)
            if resp.status_code >= 400:
                raise self._normalize_error(None, status=resp.status_code)
            data = resp.json()

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        return ModelResponse(
            id=data.get("id", f"openai_{uuid.uuid4().hex[:12]}"),
            provider=ProviderType.OPENAI.value,
            model=data.get("model", request.model),
            content=message.get("content") or "",
            finish_reason=choice.get("finish_reason") or "",
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            latency_ms=latency_ms,
            metadata={"provider": "openai"},
        )

    async def health_check(self, model: str | None = None) -> ProviderHealth:
        try:
            await self.validate_configuration(self._config)
            return ProviderHealth(
                status="healthy", provider=ProviderType.OPENAI.value, model=model or ""
            )
        except ProviderError as exc:
            return ProviderHealth(
                status="degraded", provider=ProviderType.OPENAI.value, error=exc.message
            )


# ---------------------------------------------------------------------------
# Anthropic adapter (Messages API) — spec §11
# ---------------------------------------------------------------------------
class AnthropicProviderAdapter:
    provider_type = ProviderType.ANTHROPIC

    def __init__(
        self, config: dict[str, Any] | None = None, settings: Settings | None = None
    ) -> None:
        self._config = config or {}
        self._settings = settings or get_settings()

    def _base_url(self) -> str:
        return validate_base_url(
            self._config.get("base_url") or "https://api.anthropic.com",
            allow_local=self._settings.is_development,
        )

    async def validate_configuration(self, config: dict[str, Any]) -> None:
        if not config.get("api_key"):
            raise ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "Anthropic API key is required."
            )
        validate_base_url(
            config.get("base_url") or "https://api.anthropic.com",
            allow_local=self._settings.is_development,
        )

    def _normalize_error(self, exc: Exception | None, status: int | None = None) -> ProviderError:
        if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            return ProviderError(ErrorCategory.TIMEOUT_ERROR, "The Anthropic provider timed out.")
        if status == 401:
            return ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "Anthropic authentication failed."
            )
        if status == 403:
            return ProviderError(
                ErrorCategory.AUTHORIZATION_ERROR, "Anthropic authorization failed."
            )
        if status == 429:
            return ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "Anthropic rate limit exceeded.")
        if status == 400:
            return ProviderError(
                ErrorCategory.INVALID_REQUEST_ERROR, "Invalid request to Anthropic."
            )
        if status == 404:
            return ProviderError(ErrorCategory.MODEL_NOT_FOUND, "Anthropic model not found.")
        if status and status >= 500:
            return ProviderError(ErrorCategory.PROVIDER_UNAVAILABLE, "Anthropic is unavailable.")
        return ProviderError(ErrorCategory.UNKNOWN_PROVIDER_ERROR, "Unknown Anthropic error.")

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        key = get_api_key(self.provider_type.value, self._config)
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        system_msg = next(
            (m["content"] for m in request.messages if m.get("role") == "system"), None
        )
        user_msgs = [m for m in request.messages if m.get("role") != "system"]
        body: dict[str, Any] = {
            "model": request.model,
            "messages": user_msgs,
            "max_tokens": request.max_tokens or 1024,
        }
        if system_msg:
            body["system"] = system_msg
        if request.temperature is not None:
            body["temperature"] = request.temperature
        elif request.top_p is not None:
            body["top_p"] = request.top_p

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=request.timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url()}/v1/messages", headers=headers, json=body
                )
            except Exception as exc:
                raise self._normalize_error(exc)
            if resp.status_code >= 400:
                raise self._normalize_error(None, status=resp.status_code)
            data = resp.json()

        latency_ms = int((time.perf_counter() - start) * 1000)
        content = "".join(
            part.get("text", "")
            for part in (data.get("content") or [])
            if part.get("type") == "text"
        )
        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        return ModelResponse(
            id=data.get("id", f"anthropic_{uuid.uuid4().hex[:12]}"),
            provider=ProviderType.ANTHROPIC.value,
            model=data.get("model", request.model),
            content=content,
            finish_reason=data.get("stop_reason") or "",
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            latency_ms=latency_ms,
            metadata={"provider": "anthropic"},
        )

    async def health_check(self, model: str | None = None) -> ProviderHealth:
        try:
            await self.validate_configuration(self._config)
            return ProviderHealth(
                status="healthy", provider=ProviderType.ANTHROPIC.value, model=model or ""
            )
        except ProviderError as exc:
            return ProviderHealth(
                status="degraded", provider=ProviderType.ANTHROPIC.value, error=exc.message
            )


# ---------------------------------------------------------------------------
# Google Gemini adapter (generateContent REST) — spec §12
# ---------------------------------------------------------------------------
class GeminiProviderAdapter:
    provider_type = ProviderType.GOOGLE

    def __init__(
        self, config: dict[str, Any] | None = None, settings: Settings | None = None
    ) -> None:
        self._config = config or {}
        self._settings = settings or get_settings()

    def _base_url(self) -> str:
        return validate_base_url(
            self._config.get("base_url") or "https://generativelanguage.googleapis.com",
            allow_local=self._settings.is_development,
        )

    async def validate_configuration(self, config: dict[str, Any]) -> None:
        if not config.get("api_key"):
            raise ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "Google Gemini API key is required."
            )
        validate_base_url(
            config.get("base_url") or "https://generativelanguage.googleapis.com",
            allow_local=self._settings.is_development,
        )

    def _normalize_error(self, exc: Exception | None, status: int | None = None) -> ProviderError:
        if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            return ProviderError(ErrorCategory.TIMEOUT_ERROR, "The Gemini provider timed out.")
        if status == 400 and "API key not valid" in str(getattr(exc, "message", "")):
            return ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "Gemini authentication failed."
            )
        if status == 401:
            return ProviderError(
                ErrorCategory.AUTHENTICATION_ERROR, "Gemini authentication failed."
            )
        if status == 403:
            return ProviderError(ErrorCategory.AUTHORIZATION_ERROR, "Gemini authorization failed.")
        if status == 429:
            return ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "Gemini rate limit exceeded.")
        if status == 400:
            return ProviderError(ErrorCategory.INVALID_REQUEST_ERROR, "Invalid request to Gemini.")
        if status == 404:
            return ProviderError(ErrorCategory.MODEL_NOT_FOUND, "Gemini model not found.")
        if status and status >= 500:
            return ProviderError(ErrorCategory.PROVIDER_UNAVAILABLE, "Gemini is unavailable.")
        return ProviderError(ErrorCategory.UNKNOWN_PROVIDER_ERROR, "Unknown Gemini error.")

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        key = get_api_key(self.provider_type.value, self._config)
        contents = [
            {
                "role": m.get("role", "user") == "assistant" and "model" or "user",
                "parts": [{"text": m.get("content", "")}],
            }
            for m in request.messages
        ]
        generation_config: dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_tokens
        if request.top_p is not None:
            generation_config["topP"] = request.top_p
        body = {"contents": contents, "generationConfig": generation_config}

        start = time.perf_counter()
        url = f"{self._base_url()}/v1beta/models/{request.model}:generateContent"
        async with httpx.AsyncClient(timeout=request.timeout) as client:
            try:
                resp = await client.post(url, params={"key": key}, json=body)
            except Exception as exc:
                raise self._normalize_error(exc)
            if resp.status_code >= 400:
                raise self._normalize_error(None, status=resp.status_code)
            data = resp.json()

        latency_ms = int((time.perf_counter() - start) * 1000)
        candidate = (data.get("candidates") or [{}])[0]
        parts = ((candidate.get("content") or {}).get("parts")) or []
        content = "".join(part.get("text", "") for part in parts)
        usage = data.get("usageMetadata") or {}
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)
        return ModelResponse(
            id=f"gemini_{uuid.uuid4().hex[:12]}",
            provider=ProviderType.GOOGLE.value,
            model=request.model,
            content=content,
            finish_reason=(candidate.get("finishReason") or ""),
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            latency_ms=latency_ms,
            metadata={"provider": "google"},
        )

    async def health_check(self, model: str | None = None) -> ProviderHealth:
        try:
            await self.validate_configuration(self._config)
            return ProviderHealth(
                status="healthy", provider=ProviderType.GOOGLE.value, model=model or ""
            )
        except ProviderError as exc:
            return ProviderHealth(
                status="degraded", provider=ProviderType.GOOGLE.value, error=exc.message
            )


# ---------------------------------------------------------------------------
# Adapter registry + ModelGateway orchestration
# ---------------------------------------------------------------------------
def build_adapter(
    provider_type: str, config: dict[str, Any], settings: Settings | None = None
) -> ProviderAdapter:
    pt = provider_type.upper()
    if pt == ProviderType.LOCAL.value:
        return LocalProviderAdapter(config, settings)
    if pt == ProviderType.OPENAI.value:
        return OpenAIProviderAdapter(config, settings)
    if pt == ProviderType.ANTHROPIC.value:
        return AnthropicProviderAdapter(config, settings)
    if pt in (ProviderType.GOOGLE.value, ProviderType.CUSTOM.value):
        return GeminiProviderAdapter(config, settings)
    raise ProviderError(
        ErrorCategory.INVALID_REQUEST_ERROR, f"Unsupported provider type: {provider_type}"
    )
