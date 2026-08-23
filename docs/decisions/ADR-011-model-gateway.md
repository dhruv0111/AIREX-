# ADR-011: Model Gateway with Retry, Timeout & Telemetry

**Status:** Accepted

## Context

The Model Gateway is the single choke point for every model invocation in AIREX
(spec §10–§16; PRD §5.4). It must normalize errors, enforce invocation limits,
apply retries with backoff, respect timeouts, capture latency and token usage,
record every invocation for audit/observability, and emit Prometheus metrics —
without leaking provider-specific behavior into services or the API layer.

## Decision

Add `app/integrations/gateway.py` exposing `ModelGatewayService` with:

- `invoke(...)`:
  1. validates the invocation (max tokens in `(0, model_max_tokens_max]`,
     temperature in `[0, model_temperature_max]`),
  2. builds the adapter for the provider type,
  3. runs the call through `run_with_retry` (exponential backoff, jitter, only
     transient `ErrorCategory` values are retried; permanent errors short-circuit),
  4. records a `ModelInvocation` row (request_id, tokens, latency, error
     category) on success and on failure, and
  5. emits `airex_model_*` counters/histograms (requests, errors by category,
     duration, input/output tokens).
- `health(...)` — delegates to the adapter's `health_check`, updates provider
  status, and returns `ProviderHealth`.
- `validate_invocation(...)` — shared bounds check reused by services.

Retry behavior is configurable per model via `configuration.retry_policy`
(`max_retries`, `initial_delay_ms`, `max_delay_ms`, `backoff_multiplier`);
timeout comes from settings (`model_invoke_timeout_seconds`) and can be
overridden per request.

## Alternatives

- Retry in each adapter — duplicated logic, inconsistent backoff, no global
  policy knob.
- Retry in the API router — couples transport concerns with business logic and
  makes service-layer tests impossible.
- No retries — transient 429/503/timeouts would surface directly to callers,
  contradicting the reliability goals of the platform.
- A separate worker/queue for invocations — adds latency and complexity for a
  synchronous, latency-sensitive operation.

## Consequences

- Pros: uniform error codes (`RATE_LIMIT_ERROR`, `TIMEOUT_ERROR`, …) across all
  providers; a single place to enforce limits, retries, audit, and metrics;
  invocation telemetry is queryable from the DB and Prometheus; tests use a
  flaky/stub adapter to prove retry behavior without network access.
- Cons: the gateway adds a mandatory hop for all invocations; misconfigured
  retry policies could magnify failures (mitigated by bounded `max_retries` and
  max backoff); the invocation record write is on the request path (cheap single
  insert).
