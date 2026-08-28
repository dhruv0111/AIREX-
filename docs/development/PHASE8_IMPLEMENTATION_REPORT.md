# AIREX Phase 8 — Production AI Observability, Tracing, Monitoring & Alerting

**Status: IMPLEMENTED** · Date: 2026-08-25 · Scope: Phases 0–7 complete, Phase 8 built end-to-end.

Phase 8 adds the production AI observability layer to AIREX: ingestion, tracing, spans,
cost/latency/error tracking, sampling, privacy, retention, dashboards, an alert engine with
webhook notifications, RBAC, multi-tenant isolation, audit, Prometheus metrics, and the
official Python SDK.

> **Honesty notice:** Items that require a running Docker stack (full PostgreSQL migration
> verification, live webhook endpoint, browser E2E execution) are reported as **NOT EXECUTED**,
> never as PASS. All backend unit/integration/security tests were executed and pass locally.

---

## 1. Architecture

The Phase 8 production workflow reuses the existing modular-monolith architecture
(ADR-001, ADR-005, ADR-011):

```text
Production AI Application
        ↓  (AIREX SDK / ingestion API)
AIREX SDK / API (packages/airex-python, POST /api/v1/observability/ingest)
        ↓  202 Accepted
Worker queue (Redis / in-memory)  →  existing async worker
        ↓  batch insert
PostgreSQL (traces, spans, model_pricings, alert_rules, alerts)
        ↓  aggregation (dashboard APIs)  →  Next.js frontend
        ↓  periodic alert evaluation  →  incidents + HMAC webhook notifications
        ↓  Prometheus metrics
```

Reused (not duplicated): authentication, RBAC/permissions, multi-tenancy (org → project →
environment), the worker, ModelGateway/provider abstraction, audit repository, error
envelope, Prometheus middleware, and the existing frontend app shell / UI components.

## 2. Observability Model

- **Observability modes** (§5): `METADATA_ONLY` (default), `HASHED_CONTENT`, `FULL_CONTENT`,
  stored per project in `projects.settings` and applied inside the ingestion pipeline.
- **Privacy** (§4): raw prompts/responses are never stored by default; only metadata, hashes
  (in HASHED_CONTENT), token counts, latency, model, provider, status, error, cost, and trace
  metadata. Configurable best-effort redaction in FULL_CONTENT mode.
- **Retention** (§6): per-project `retention_days`; the worker’s periodic scheduler deletes
  expired traces and spans via `clean_observability_retention_for_session`.
- **Sampling** (§23–24): per-project `sample_rate` in `[0.0, 1.0]` with validated bounds;
  errors may bypass sampling (`error_bypass_sampling`, default true).

## 3. Trace Model

Trace fields (§8): `trace_id`, `project_id`, `organization_id`, `environment`,
`service_name`, `operation_name`, `start_time`, `end_time`, `duration_ms`, `status`,
`error`, optional `user_id` / `session_id`, `deployment_version`, `git_commit`, and
`quality_score`.

## 4. Span Model

Span fields (§9–10): `span_id`, `trace_id`, `parent_span_id`, `span_type`
(LLM / RETRIEVAL / TOOL / PROMPT / EVALUATION / CUSTOM), `name`, `start_time`, `end_time`,
`duration_ms`, `status`, `attributes`. LLM spans additionally record `provider`, `model`,
`input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost`, `temperature`,
`max_tokens`, and `error_category`. API keys are never stored.

## 5. Ingestion

- Endpoints: `POST /api/v1/observability/ingest` (batched traces + spans, `202 Accepted`),
  plus `GET .../overview`, `.../traces`, `.../models`, `.../providers`, `.../cost`,
  `.../latency`, `.../settings`, and `GET /api/v1/observability/traces/{trace_id}`.
- Async ingestion (§18): the API enqueues a job; the worker performs batch inserts.
- Idempotency/deduplication (§19): duplicate `(project, trace_id)` and `(trace_id, span_id)`
  rows are skipped.
- Bounded payloads (§17): batches are limited (≤1000 traces, ≤5000 spans); oversized
  payloads return `400` (AT-P8-029).
- Deterministic, sampled, privacy-filtered storage via `ObservabilityService.ingest_batch`.

## 6. Cost Calculation

- Versioned `model_pricings` table (§11): `model_pattern`, provider, `input_price_per_1k`,
  `output_price_per_1k`, `currency`, `effective_from`, `effective_until`; managed by a
  pricing API (`GET/POST/PATCH/DELETE /api/v1/pricing`).
- `calculate_span_cost` (§12) uses `Decimal`, wildcard pattern matching
  (`gpt-4o*`), and returns `None` when pricing or token counts are missing (§11, AT-P8-008).
- Example verified: 1000 input @ $0.005/1K + 500 output @ $0.015/1K = `$0.0125` (AT-P8-007).

## 7. Latency & Errors

- Latency (§13): `p50/p90/p95/p99`, average, and max computed from stored trace/span
  durations. TTFT is not invented when streaming data is unavailable.
- Errors (§14): normalized `error_category` (authentication, authorization, rate_limit,
  timeout, network, invalid_request, provider, model, internal, unknown). Request statuses
  (§15): `SUCCESS`, `ERROR`, `TIMEOUT`, `CANCELLED`, `RATE_LIMITED`.

## 8. SDK (packages/airex-python)

- `from airex import AirexClient` with `trace(...)`, `span(...)`, `observe_llm(...)`,
  `record_quality(...)` context managers that auto-generate trace/span IDs, capture latency,
  token usage, and errors.
- Batching (§64): events buffer in a bounded local queue; flush on batch size / interval /
  shutdown / manual flush. Backpressure (§65): queue-full drops events (dropped-event counter)
  instead of blocking the application. Failure isolation (§21): fail-silent by default,
  `AIREX_SDK_DISABLED=true` (AT-P8-027).
- Config via env (§22): `AIREX_API_URL`, `AIREX_API_TOKEN`, `AIREX_PROJECT_ID`,
  `AIREX_ENVIRONMENT`, `AIREX_SERVICE_NAME`, `AIREX_OBSERVABILITY_MODE`, `AIREX_SAMPLE_RATE`.

## 9. Dashboards

- `/projects/[id]/observability` — requests, success/error rate, latency percentiles, tokens,
  cost, and model/provider breakdowns with selectable time ranges (§25–§33).
- `/projects/[id]/observability/traces` — paginated trace explorer with status/provider/
  trace-ID/time filters (§34, §36).
- `/projects/[id]/observability/traces/[traceId]` — trace detail with span hierarchy,
  LLM invocations, tokens, and cost (§35).
- Empty states show “No observability data yet…” and real `N/A` (never fake `$0`/`0%`/`0ms`);
  backend errors show “Unable to load observability data. Try again.” (§69–§70).
- Charts use the existing Recharts stack; no fake data is rendered (§82).

## 10. Alerting & Anomaly Detection

- **Anomaly detection** (§40): simple, explainable, non-ML strategies — `threshold`,
  `moving_average`, `standard_deviation` (`app/evaluations/anomaly.py`).
- **Alert rules** (§41): metric (`error_rate`, `latency_p95`, `cost`, `token_usage`,
  `request_rate`, `quality_score`), operator, threshold, window, cooldown, severity
  (`INFO`..`CRITICAL`), environment, enabled flag.
- **Lifecycle** (§43–45): `TRIGGERED` → (deduplicate while true, `occurrence_count`) →
  `ACKNOWLEDGED` → `RESOLVED`. Deduplication creates one active incident (AT-P8-020).
- **Notifications** (§46–49): `NotificationProvider` abstraction with an HMAC-signed
  `WebhookNotificationProvider` (`X-Airex-Timestamp`, `X-Airex-Signature`); secrets never
  appear in payloads (AT-P8-024); failures are recorded without breaking alert state.
- **Scheduling**: the worker’s periodic scheduler evaluates all enabled rules (~60s cadence)
  and runs retention cleanup.
- **UI**: `/projects/[id]/alerts` (active/history, acknowledge) and `/projects/[id]/alerts/rules`
  (create/edit/disable/delete).

## 11. Security, RBAC, Multi-Tenancy, Audit

- **RBAC** (§54): VIEWER read-only; write operations (alert rules, observability settings,
  pricing) require a non-viewer role (`403` for viewers).
- **Multi-tenant isolation** (§55): cross-org/project trace access returns `403/404`
  (AT-P8-017); IDs from the client are never trusted; service tokens enforce project
  boundaries in `deps.py`.
- **Audit** (§56): `OBSERVABILITY_CONFIG_UPDATED`, `QUALITY_SIGNAL_RECORDED`,
  `ALERT_RULE_*`, `ALERT_TRIGGERED/ACKNOWLEDGED/RESOLVED`, `NOTIFICATION_*` (spans are not
  audited individually).
- **Prometheus** (§57): `airex_observability_ingested_total`, `airex_observability_ingestion_errors_total`,
  `airex_trace_duration_seconds`, `airex_llm_requests_total`, `airex_llm_errors_total`,
  `airex_llm_tokens_total`, `airex_llm_cost_total`, `airex_alerts_triggered_total`,
  `airex_alerts_resolved_total`, `airex_notifications_sent_total`,
  `airex_notifications_failed_total` — no high-cardinality labels.

## 12. API Summary

```text
POST /api/v1/observability/ingest
GET  /api/v1/projects/{id}/observability/overview | models | providers | cost | latency | settings
PUT  /api/v1/projects/{id}/observability/settings
GET  /api/v1/observability/traces/{trace_id}
GET  /api/v1/projects/{id}/observability/traces
POST /api/v1/projects/{id}/observability/quality-signals
GET  /api/v1/projects/{id}/alerts
GET  /api/v1/projects/{id}/alerts/{alert_id}
POST /api/v1/projects/{id}/alerts/{alert_id}/ack
GET  /api/v1/projects/{id}/alert-rules
POST /api/v1/projects/{id}/alert-rules
PATCH/DELETE /api/v1/alert-rules/{id}
GET/POST/PATCH/DELETE /api/v1/pricing
```

## 13. Frontend

New project-navigation links **Observability** and **Alerts** were added to the project page.
Pages built: observability dashboard, trace explorer, trace detail (span hierarchy), alerts
(active/history/acknowledge), and alert rules (create/disable/delete). API client methods and
shared types were added for all Phase 8 endpoints. `tsc --noEmit` passes and `next build`
succeeds with all new routes.

## 14. Metrics

Phase 8 Prometheus metrics are defined in [`app/core/metrics.py`](../../apps/api/app/core/metrics.py)
and incremented on ingestion and alert lifecycle events (see §11). A `/metrics` endpoint is
exposed when `PROMETHEUS_ENABLED`.

## 15. Testing

### Executed (local, all pass)

| Area | Result |
|------|--------|
| Backend full suite (unit + integration + security) | **PASS — 548 tests, exit 0** |
| Phase 8 unit tests (`test_phase8.py`, `test_phase8_alerts.py`) | **PASS — 25 tests** |
| Phase 8 integration tests (`test_phase8_observability.py`) | **PASS — 11 tests** |
| Phase 8 security tests (`test_phase8_security.py`) | **PASS — 2 tests** |
| Ingestion load benchmark (10,000 spans, `scripts/bench_observability.py`) | **PASS — 20,000 events, ~1522 events/s, no duplicates** |
| Frontend `tsc --noEmit` | **PASS** |
| Frontend `next build` | **PASS** |
| Migration chain `alembic history` (0009 = head) | **PASS (chain consistent)** |

### Coverage (Phase 8 modules, via pytest-cov)

| Module | Coverage |
|--------|----------|
| `services/observability.py` (ingestion) | 93% |
| `evaluations/cost.py` (cost engine) | 96% |
| `evaluations/anomaly.py` | 76% |
| `evaluations/alert_engine.py` | 86% |
| `repositories/observability.py` | 85% |
| `api/v1/observability.py` | 88% |
| `api/v1/alerts.py` | 65% |
| `api/v1/pricing.py` | 89% |
| `schemas/observability.py`, `schemas/alert.py`, `schemas/pricing.py` | 97–100% |
| **Phase 8 modules (TOTAL)** | **87%** |

### Not executed (requires Docker/browser stack)

- Browser E2E execution of `tests/e2e/tests/observability.spec.ts` and `alerts.spec.ts`
  (specs written; execution requires the full Docker stack + Playwright browser).
- Docker `docker compose down -v && docker compose up --build` verification (§89).
- Full PostgreSQL upgrade/downgrade/upgrade migration run (§88).

## 16. Performance

Ingestion is asynchronous (queue → worker → batch inserts), payloads are bounded, lookups
are indexed (`trace_id`, `span_id`, project + time), aggregation is computed server-side, and
sampling + retention bound storage growth (spec §59). See §15 benchmark for local numbers.

## 17. Known Limitations

- Alert evaluation runs on a periodic worker cadence (~60s), not sub-second.
- Cost accuracy depends on operator-maintained pricing configuration; missing pricing shows
  `N/A` (never fabricated).
- `FULL_CONTENT` redaction is best-effort and not a guarantee of perfect PII detection (§61).
- No separate time-series database: PostgreSQL aggregation is used at current scale (§58).
- TTFT is not recorded when streaming data is unavailable (§13).
- Anomaly detection is threshold/moving-average/std-dev based, deliberately not ML (§40).
- GitHub/GitLab live integration was NOT tested in Phase 8 (unchanged from Phase 7).

---

## Acceptance Results (AT-P8)

| ID | Criterion | Result |
|----|-----------|--------|
| AT-P8-001 | Ingest trace → 202 | **PASS** |
| AT-P8-002 | Ingest span | **PASS** |
| AT-P8-003 | Duplicate span rejected/deduplicated | **PASS** |
| AT-P8-004 | Trace appears in explorer | **PASS** |
| AT-P8-005 | Trace detail displays spans | **PASS** |
| AT-P8-006 | Token usage recorded | **PASS** |
| AT-P8-007 | Known pricing → correct cost | **PASS** |
| AT-P8-008 | Missing pricing → null cost | **PASS** |
| AT-P8-009 | Latency metrics calculated | **PASS** |
| AT-P8-010 | Error metrics calculated | **PASS** |
| AT-P8-011 | Sampling rate 0 stores no normal traces | **PASS** |
| AT-P8-012 | Sampling rate 1 stores all eligible traces | **PASS** |
| AT-P8-013 | Error trace bypasses sampling when configured | **PASS** |
| AT-P8-014 | Privacy mode does not store prompt content | **PASS** |
| AT-P8-015 | Full content mode only when explicitly enabled | **PASS** |
| AT-P8-016 | Retention deletes expired data | **PASS** |
| AT-P8-017 | Cross-org trace access rejected | **PASS** |
| AT-P8-018 | Viewer cannot modify alert rules | **PASS** |
| AT-P8-019 | Alert triggers when threshold crossed | **PASS** |
| AT-P8-020 | Alert deduplicates repeated violations | **PASS** |
| AT-P8-021 | Alert resolves when condition normalizes | **PASS** |
| AT-P8-022 | Alert acknowledgement works | **PASS** |
| AT-P8-023 | Webhook notification sent (mocked endpoint) | **PASS** |
| AT-P8-024 | Webhook secret is not leaked | **PASS** |
| AT-P8-025 | Prometheus observability metrics generated | **PASS** |
| AT-P8-026 | SDK captures model invocation | **PASS** |
| AT-P8-027 | SDK failure does not break application | **PASS** |
| AT-P8-028 | SDK batching works | **PASS** |
| AT-P8-029 | Oversized ingestion rejected (400) | **PASS** |
| AT-P8-030 | Phase 0–7 regression suite remains green | **PASS** |

## Frontend Acceptance (AT-P8-UI)

| ID | Criterion | Result |
|----|-----------|--------|
| AT-P8-UI-001 | Observability dashboard loads | **NOT EXECUTED** (spec written; E2E requires Docker stack) |
| AT-P8-UI-002 | Time-range filtering works | **NOT EXECUTED** (as above) |
| AT-P8-UI-003 | Request metrics display | **NOT EXECUTED** (as above) |
| AT-P8-UI-004 | Latency charts display | **NOT EXECUTED** (as above) |
| AT-P8-UI-005 | Cost metrics display | **NOT EXECUTED** (as above) |
| AT-P8-UI-006 | Model breakdown displays | **NOT EXECUTED** (as above) |
| AT-P8-UI-007 | Provider breakdown displays | **NOT EXECUTED** (as above) |
| AT-P8-UI-008 | Trace explorer loads | **NOT EXECUTED** (as above) |
| AT-P8-UI-009 | Trace detail loads | **NOT EXECUTED** (as above) |
| AT-P8-UI-010 | Span hierarchy displays | **NOT EXECUTED** (as above) |
| AT-P8-UI-011 | Alert list loads | **NOT EXECUTED** (as above) |
| AT-P8-UI-012 | Alert rule creation works | **NOT EXECUTED** (as above) |
| AT-P8-UI-013 | Alert acknowledgement works | **NOT EXECUTED** (as above) |
| AT-P8-UI-014 | Alert resolution displays | **NOT EXECUTED** (as above) |
| AT-P8-UI-015 | Empty state works | **NOT EXECUTED** (as above) |
| AT-P8-UI-016 | Error state works | **NOT EXECUTED** (as above) |
| AT-P8-UI-017 | Viewer cannot modify alert rules | **NOT EXECUTED** (as above) |

All frontend pages are built, compile (`tsc --noEmit`), and pass `next build`. The UI
acceptance criteria are implemented in `tests/e2e/tests/observability.spec.ts` and
`alerts.spec.ts`; execution requires bringing up the Docker stack and a Playwright browser,
which was not available in this environment (Docker daemon not running).

## Final Status

- Backend implementation: **COMPLETE**
- Frontend implementation: **COMPLETE**
- Backend tests (incl. Phase 0–7 regression): **PASS (548)**
- Load benchmark: **PASS**
- Docker verification: **NOT EXECUTED** (Docker daemon unavailable)
- Migration PostgreSQL verification: **NOT EXECUTED** (requires Docker); chain verified via `alembic history`
- Browser E2E execution: **NOT EXECUTED** (requires Docker stack)
- Documentation & ADRs: **COMPLETE** (ADR-030, ADR-031, ADR-032, README updated)

**Phase 8 gate (backend + build + tests): PASS.** Docker/E2E-dependent criteria remain
`NOT EXECUTED` until the Docker stack is available.
