# ADR-030: Observability Data Model

- Status: Accepted
- Date: 2026-08-25
- Phase: 8
- Deciders: AIREX Engineering
- Related: ADR-002 (PostgreSQL), ADR-005 (Redis background jobs), ADR-011 (Model Gateway)

## Context

AIREX needs to answer: "What is happening with my AI system in production, how is it
performing, how much does it cost, where is it failing, and when should I be alerted?"
This requires a production observability data model for traces, spans, model
invocations, token usage, cost, latency, errors, and quality signals.

## Decision

### Trace / Span Model

- A **Trace** represents one end-to-end AI workflow and is keyed by a client-supplied
  `trace_id` (unique per project). It carries project/organization scope, environment,
  service/operation names, status, duration, optional user/session correlation, and
  deployment/git metadata.
- A **Span** represents one unit of work within a trace (LLM, RETRIEVAL, TOOL, PROMPT,
  EVALUATION, CUSTOM) keyed by `(trace_id, span_id)`, with `parent_span_id` for hierarchy.
- LLM spans record provider, model, token counts, estimated cost, temperature, max tokens,
  latency, status, and a normalized `error_category`.

### Storage

- Use the existing PostgreSQL database. No separate time-series database is introduced in
  Phase 8. Indexed lookups (`trace_id`, `span_id`, project + time) and aggregation queries
  are sufficient for the current scale (spec §58).
- Ingestion is asynchronous: the API enqueues batches onto the existing worker queue
  (ADR-005), and the worker performs batch inserts via the repository. Duplicate
  `(project, trace_id)` / `(trace_id, span_id)` rows are deduplicated.

### Versioned Pricing Configuration

- Cost is never hardcoded in business logic. A versioned `model_pricings` table
  (`model_pattern`, provider, input/output price per 1K, currency, effective range) is
  managed through a pricing API. When no pricing matches, cost is `null` — never fabricated.

### Reuse

- Tenant isolation reuses the existing organization → project → environment model.
- Authentication/RBAC and audit infrastructure are reused unchanged.

## Consequences

- Trace/span lookup and dashboard aggregations run on proven PostgreSQL infrastructure.
- Deduplication and sampling keep storage bounded.
- Cost accuracy depends on operator-maintained pricing configuration; absent pricing shows `N/A`.
