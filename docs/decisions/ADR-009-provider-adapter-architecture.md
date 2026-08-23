# ADR-009: Provider Adapter Architecture

**Status:** Accepted

## Context

Phase 1 must integrate with OpenAI, Anthropic, Gemini, and a local development
provider while keeping business logic provider-agnostic (PRD §2.6, §5; spec
§5–§16). Every provider has a different API shape (URLs, request bodies, auth
headers, response schemas) and a different error vocabulary. Tests must run
without paid API keys or real network calls.

## Decision

Introduce a single `ProviderAdapter` protocol with one class per provider:

- `LocalProviderAdapter` — deterministic, configurable failure modes and latency,
  no network required.
- `OpenAIProviderAdapter`, `AnthropicProviderAdapter`, `GeminiProviderAdapter` —
  thin `httpx` clients (no vendor SDKs) that translate the provider's HTTP API
  into the internal `ModelRequest` / `ModelResponse` model.

Each adapter implements:

- `invoke(request) -> ModelResponse`
- `health_check(model) -> ProviderHealth`
- `validate_configuration(config) -> None`

All adapters share a normalized error taxonomy (`ErrorCategory`) and map HTTP
status codes to a typed `ProviderError`, which the API layer surfaces through the
standard error envelope (`{error: {code, message, request_id}}`).

`build_adapter(provider_type, config)` is the factory used by services and the
gateway. No provider SDK is required at install time; `httpx` is the only HTTP
transport.

## Alternatives

- Vendor SDKs per provider (`openai`, `anthropic`, `google-genai`) — heavier
  dependency footprint, three divergent error models, harder to mock, slower to
  evolve, and several SDKs had no CPython 3.14 wheels at the time of writing.
- A single mega-client with provider branching — violates single responsibility
  and makes per-provider testing painful.
- Only HTTP passthrough without normalization — pushes provider-specific error
  handling into business logic.

## Consequences

- Pros: provider additions are additive (new class + factory entry); tests mock
  `httpx.AsyncClient`, never hit the network; a uniform error vocabulary keeps
  the gateway, metrics, and UI simple; zero paid-account requirement for
  development (LOCAL adapter).
- Cons: each new provider requires a bespoke adapter; the mapping layer must be
  kept in sync with provider API changes; error normalization is a best-effort
  mapping and unknown statuses fall back to `UNKNOWN_PROVIDER_ERROR`.
