# ADR-006: Provider Abstraction (Model Gateway)

**Status:** Accepted

## Context
Business logic must never depend on a specific AI provider (spec §2.6). Paid providers (OpenAI/Anthropic/Gemini) must not be required for development.

## Decision
Define a `ModelGateway` port with a `LocalProviderGateway` implementation used by default. Provider adapters for OpenAI/Anthropic/Gemini are activated only when their keys are configured (Phase 1). No paid provider is called unless explicitly configured; no fake external service is fabricated.

## Alternatives
- Direct SDK calls in services — violates §2.6 (prohibited #5).
- Fake paid providers — violates "do not fake external services".

## Consequences
- Pros: business logic is provider-agnostic; local development needs no paid account.
- Cons: an extra interface layer; adapters must be implemented per provider (Phase 1).
