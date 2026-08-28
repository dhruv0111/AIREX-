# ADR-032: Alert Engine

- Status: Accepted
- Date: 2026-08-25
- Phase: 8
- Deciders: AIREX Engineering
- Related: ADR-030 (Observability data model), ADR-005 (Redis background jobs)

## Context

AIREX must alert operators when production AI metrics cross thresholds (error rate,
latency, cost, tokens, request rate, quality) without flooding them with duplicate
notifications, and must allow acknowledgement and automatic recovery.

## Decision

### Explainable Anomaly Detection

Phase 8 starts with simple, explainable, non-ML anomaly detection (spec §40):
- `threshold` comparisons with an operator (`>`, `>=`, `<`, `<=`, `==`);
- `moving_average` deviation from a trailing baseline (e.g. +30%);
- `standard_deviation` (z-score) deviation from the historical mean.

These pure, deterministic helpers are used for unit testing and future rule strategies.

### Alert Rules

Alert rules are configurable per project (create/edit/disable/delete):
metric, operator, threshold, window (`duration_seconds`), `cooldown_seconds`,
severity (`INFO`..`CRITICAL`), optional environment, and enabled flag.

### Alert Lifecycle

- `TRIGGERED` when the sliding-window metric crosses the threshold.
- **Deduplication**: while the condition remains true, the same active incident is
  updated (`last_seen_at`, `occurrence_count`) rather than creating new alerts.
- `ACKNOWLEDGED` records an acknowledgement without resolving the underlying condition.
- `RESOLVED` when the metric returns to normal; resolution time is recorded.

### Notification Abstraction

- A `NotificationProvider` abstraction with an HMAC-signed `WebhookNotificationProvider`
  (`X-Airex-Timestamp` + `X-Airex-Signature`). Secrets are never sent in payloads.
- Payloads contain alert metadata (id, severity, metric, threshold, observed, status,
  project_id) — no secrets, no prompts, no responses.

### Scheduling

- The worker's periodic scheduler evaluates all enabled rules (~60s cadence) and runs
  retention cleanup. Alert state changes and notification outcomes are emitted as
  Prometheus metrics (`airex_alerts_triggered_total`, `airex_alerts_resolved_total`,
  `airex_notifications_sent_total`, `airex_notifications_failed_total`).

### RBAC

- Viewers can view alerts/rules but cannot create/edit/disable/delete rules or update
  observability settings (403). Write operations reuse existing role checks.

## Consequences

- Real alerts are produced by the actual engine (no seeded/fake alerts).
- Deduplication prevents notification storms while preserving incident history.
- Simple, explainable detection keeps alert messages auditable and unit-testable.
