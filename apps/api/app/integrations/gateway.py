"""Model Gateway orchestration (spec §5, §14–§16, §30, §55; ADR-011).

Business logic calls the gateway with a provider configuration; the gateway
builds the correct adapter, applies retry/timeout policies, validates model
parameters, and records observability metrics. Provider-specific objects never
leave this module.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import ValidationFailure
from app.core.metrics import (
    model_input_tokens_total,
    model_output_tokens_total,
    model_request_duration_seconds,
    model_request_errors_total,
    model_requests_total,
)
from app.integrations.provider import (
    ModelRequest,
    ModelResponse,
    ProviderError,
    ProviderHealth,
    RetryPolicy,
    build_adapter,
    run_with_retry,
)


class ModelGatewayService:
    """Provider-neutral entry point for all model calls."""

    def __init__(self, settings: Any | None = None) -> None:
        self._settings = settings or get_settings()

    def _adapter_config(
        self,
        provider_type: str,
        api_key: str | None,
        base_url: str | None,
        configuration: dict[str, Any] | None,
    ) -> dict[str, Any]:
        cfg = dict(configuration or {})
        if api_key:
            cfg["api_key"] = api_key
        if base_url:
            cfg["base_url"] = base_url
        return cfg

    def validate_invocation(
        self,
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> None:
        """Model invocation safety (spec §55): reject invalid params."""
        settings = self._settings
        if max_tokens is not None:
            if max_tokens <= 0:
                raise ValidationFailure("max_tokens must be greater than 0.")
            if max_tokens > settings.model_max_tokens_max:
                raise ValidationFailure(
                    f"max_tokens must not exceed {settings.model_max_tokens_max}."
                )
        if temperature is not None and not (0.0 <= temperature <= settings.model_temperature_max):
            raise ValidationFailure(
                f"temperature must be between 0 and {settings.model_temperature_max}."
            )

    async def invoke(
        self,
        *,
        provider_type: str,
        api_key: str | None,
        base_url: str | None,
        configuration: dict[str, Any] | None,
        request: ModelRequest,
        retry_policy: RetryPolicy | None = None,
    ) -> ModelResponse:
        self.validate_invocation(max_tokens=request.max_tokens, temperature=request.temperature)
        timeout = request.timeout or float(self._settings.model_invoke_timeout_seconds)
        request.timeout = timeout
        policy = retry_policy or RetryPolicy()
        cfg = self._adapter_config(provider_type, api_key, base_url, configuration)
        adapter = build_adapter(provider_type, cfg, self._settings)

        start = time.perf_counter()
        try:
            response = await run_with_retry(
                lambda: adapter.invoke(request), policy, timeout=timeout
            )
        except ProviderError as exc:
            model_request_errors_total.labels(
                provider=provider_type.lower(), error_category=exc.category.value
            ).inc()
            model_requests_total.labels(provider=provider_type.lower(), status="error").inc()
            raise
        finally:
            model_request_duration_seconds.labels(provider=provider_type.lower()).observe(
                time.perf_counter() - start
            )

        model_requests_total.labels(provider=provider_type.lower(), status="success").inc()
        model_input_tokens_total.labels(provider=provider_type.lower()).inc(
            response.usage.input_tokens
        )
        model_output_tokens_total.labels(provider=provider_type.lower()).inc(
            response.usage.output_tokens
        )
        return response

    async def health(
        self,
        *,
        provider_type: str,
        api_key: str | None,
        base_url: str | None,
        configuration: dict[str, Any] | None,
        model: str | None = None,
    ) -> ProviderHealth:
        cfg = self._adapter_config(provider_type, api_key, base_url, configuration)
        adapter = build_adapter(provider_type, cfg, self._settings)
        try:
            return await adapter.health_check(model)
        except ProviderError as exc:
            return ProviderHealth(
                status="unavailable",
                provider=provider_type,
                model=model or "",
                error=exc.message,
            )
