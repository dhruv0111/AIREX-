# ADR-031: Observability Privacy and Retention

- Status: Accepted
- Date: 2026-08-25
- Phase: 8
- Deciders: AIREX Engineering
- Related: ADR-030 (Observability data model), ADR-002 (PostgreSQL)

## Context

Production AI observability must not automatically store raw prompts and responses.
AIREX must be privacy-safe by default, support configurable content modes, bound data
retention, and enforce sampling so high-volume production traffic does not overwhelm
storage or violate data policy.

## Decision

### Observability Modes (project-level, default privacy-safe)

- `METADATA_ONLY` (default): raw prompt/response content is never stored. Content-like
  attribute keys (prompt, response, input, output, messages, content, completion, text,
  query) are dropped at ingestion.
- `HASHED_CONTENT`: content values are stored as SHA-256 hashes (`<key>_hash`), enabling
  exact-match analysis without storing raw text.
- `FULL_CONTENT`: raw content is stored only when explicitly enabled by project policy
  (with best-effort redaction of API keys, bearer tokens, password fields, and common
  secret patterns — not a guarantee of perfect PII detection).

The mode is stored in the project `settings` JSON and applied inside the ingestion
pipeline before persistence. Never store API keys.

### Sampling

- Each project defines `sample_rate` in `[0.0, 1.0]`, validated at the settings API.
- Normal traces are retained with probability `sample_rate` (deterministic in tests).
- Errors may bypass sampling (`error_bypass_sampling`, default true) so failures are
  always captured.

### Retention

- Each project defines `retention_days` (e.g. 7 / 30 / 90 / 180). The worker's periodic
  scheduler runs a retention cleanup task that deletes expired traces and their spans
  according to policy. Default is unset (no auto-purge) to avoid surprising data loss.

### Lifecycle

- Settings are managed via `GET/PUT /api/v1/projects/{id}/observability/settings`,
  requiring a non-viewer role. Configuration changes emit `OBSERVABILITY_CONFIG_UPDATED`
  audit events.

## Consequences

- Privacy-safe by default: no raw prompts/responses are persisted unless explicitly enabled.
- Storage is bounded by sampling + retention.
- Operators control the trade-off between data richness and privacy.
