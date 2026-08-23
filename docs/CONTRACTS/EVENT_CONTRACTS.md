# Event Contracts — AIREX

Event-driven contracts for the AIREX platform. Transport: **transactional outbox** (`outbox_events` table) → **Redis pub/sub** fan-out + **Arq job** enqueue (see [`EVENT_ARCHITECTURE.md`](../ARCHITECTURE/EVENT_ARCHITECTURE.md)). Delivery is **at-least-once**; every consumer must be **idempotent**.

---

## 1. Event Envelope (canonical)

```json
{
  "id": "01JXYZ...",                // UUID v7; global uniqueness; dedup key
  "event_type": "evaluation.completed",
  "version": 1,                     // schema version of payload
  "aggregate_type": "evaluation_run",
  "aggregate_id": "evrun_01J...",
  "organization_id": 42,
  "project_id": 7,
  "occurred_at": "2026-08-21T19:02:00.000Z",
  "actor": {"user_id": 12, "role": "engineer"},
  "trace_id": "01JZ...",            // OpenTelemetry trace linkage
  "payload": { }                    // type-specific
}
```

### Delivery semantics
| Property | Contract |
|----------|----------|
| Ordering | Per-`aggregate_id`, events are ordered by `occurred_at` (outbox insert order); consumers that need order use `aggregate_id` + `sequence`. No global ordering. |
| Idempotency | Consumers dedupe by `id` (Redis `SETNX` or DB `processed` marker on the consuming record, e.g., `notifications.dedup_key`). |
| Retry | Transient failures retried with exponential backoff (attempts tracked in outbox/consumer); permanent failures → dead-letter (DLQ) + alert. No infinite retry (§58). |
| Retention | Outbox rows purged 7 days after `processed_at`. |
| Exactly-once side effects | Not guaranteed; idempotent consumers make at-least-once equivalent to effectively-once. |

---

## 2. Event Catalogue

Legend: Producer / Consumer(s) / Payload keys / Retry class / Ordering / Idempotency.

### 2.1 user.registered
- **Producer:** Auth service (register).
- **Consumers:** Mailer (verification email), Audit.
- **Payload:** `{user_id, email, full_name}`.
- **Retry:** transient (email infra) with backoff; permanent after max.
- **Idempotency:** key = event id; email sends keyed by token to avoid duplicates.

### 2.2 user.login / user.logout
- **Producer:** Auth service.
- **Consumers:** Audit, Security monitor (anomaly later).
- **Payload:** `{user_id, email, ip, user_agent, result, timestamp}`.
- **Idempotency:** event id; audit row unique on (event_id).

### 2.3 organization.member.role_changed
- **Producer:** Org service (role change).
- **Consumers:** Audit; Session service (invalidate cached role).
- **Payload:** `{organization_id, user_id, old_role, new_role, actor_id}`.
- **Idempotency:** event id; cache invalidation idempotent.

### 2.4 project.created / project.deleted / project.archived
- **Producer:** Project service.
- **Consumers:** Audit; Cache/Index invalidator; Metrics.
- **Payload:** `{project_id, organization_id, name, archived, deleted_at}`.
- **Idempotency:** event id; cache invalidation idempotent.

### 2.5 api_key.created / api_key.deleted
- **Producer:** Admin service.
- **Consumers:** Audit; Key-revocation cache.
- **Payload:** `{api_key_id, organization_id, name, created_by, deleted_at}` (never the secret).
- **Idempotency:** event id.

### 2.6 dataset.version_created
- **Producer:** Dataset service.
- **Consumers:** Cache invalidator; Version-compare refresh.
- **Payload:** `{dataset_id, dataset_version_id, organization_id, project_id, version_no, row_count, checksum}`.
- **Idempotency:** event id; version unique constraint.

### 2.7 evaluation.created
- **Producer:** Evaluation service (POST /evaluations).
- **Consumers:** Audit; Metrics.
- **Payload:** `{evaluation_id, organization_id, project_id, environment, config_versions:{dataset,model,prompt,eval}}`.

### 2.8 evaluation.run_started
- **Producer:** Worker (run_evaluation step 2).
- **Consumers:** SSE; Notifications (start).
- **Payload:** `{run_id, evaluation_id, organization_id, project_id, job_id, started_at}`.

### 2.9 evaluation.progress
- **Producer:** Worker (throttled, e.g., every 5% or 10s).
- **Consumers:** SSE (live dashboards).
- **Payload:** `{run_id, organization_id, project_id, progress:{total,completed,passed,failed,warning}}`.
- **Ordering:** per run, increasing progress; consumers render latest.
- **Idempotency:** SSE is display-only; dedup by (run_id, completed).

### 2.10 evaluation.completed
- **Producer:** Worker (run_evaluation final).
- **Consumers:** Notifications; Regression service; Quality gate; Alert evaluator; RCA/Recommendation; Aggregation; Cache invalidator; CI callback (webhook); Audit.
- **Payload:**
```json
{
  "run_id": "evrun_..", "evaluation_id": "..",
  "organization_id": 42, "project_id": 7,
  "status": "COMPLETED",
  "metrics": {"accuracy": 0.92, "faithfulness": 0.94, "hallucination": 0.04,
              "safety": 0.97, "p95_latency_ms": 2100, "cost_per_request": 0.019},
  "score": 87.4,
  "regression_status": "pass",
  "quality_gate_status": "pass",
  "triggered_by": "ci",
  "dataset_version_id": 3, "model_ref": "gpt-4o", "prompt_version_id": 7
}
```
- **Ordering:** after `evaluation.run_started` for the same run.
- **Idempotency:** consumers keyed on `run_id`; notifications use dedup_key `eval-completed:{run_id}`.

### 2.11 evaluation.failed
- **Producer:** Worker (permanent failure / job failure).
- **Consumers:** Notifications; Alerts (model_failure type §43); Audit.
- **Payload:** `{run_id, organization_id, project_id, error:{code,message,request_id,details}}`.
- **Idempotency:** dedup on `run_id` + error.code.

### 2.12 test.generation.completed
- **Producer:** Worker (test_generation).
- **Consumers:** SSE; Notifications.
- **Payload:** `{generation_id, organization_id, project_id, requested_count, generated_count, categories:{...}}`.

### 2.13 regression.detected
- **Producer:** Regression service (from evaluation.completed consumer).
- **Consumers:** Notifications; Alerts; Dashboard; CI callback.
- **Payload:** `{regression_run_id, project_id, organization_id, baseline_experiment_id, candidate_experiment_id, verdict, deltas}`.

### 2.14 quality_gate.violated
- **Producer:** Quality gate.
- **Consumers:** CI callback (exit non-zero, AC-CICD-003); Notifications; Alerts.
- **Payload:** `{run_id, project_id, organization_id, gate:{accuracy:...}, violations:[{metric,expected,actual}]}`.

### 2.15 alert.fired
- **Producer:** Alert evaluator worker.
- **Consumers:** Notifications (in-app/email/webhook); SSE.
- **Payload:** `{alert_id, rule_id, organization_id, project_id, severity, metric, value, threshold, duration_seconds, occurred_at}`.
- **Idempotency:** dedup on (rule_id, org, window) to prevent storms.

### 2.16 trace.ingested
- **Producer:** Ingest path (POST /traces/ingest).
- **Consumers:** Aggregation; (later) anomaly detection.
- **Payload:** `{trace_id, organization_id, project_id, started_at, duration_ms, token_usage, cost, status, error}`.

### 2.17 notification.requested
- **Producer:** Any service needing to notify (via outbox).
- **Consumers:** Notifier worker.
- **Payload:** `{notification_id, organization_id, user_id?, kind, channel, payload, dedup_key}`.
- **Retry:** per-channel: email/webhook retry w/ backoff; in-app immediate.
- **Idempotency:** `dedup_key` unique on notifications.

### 2.18 report.generated / export.completed
- **Producer:** Report/Export worker.
- **Consumers:** SSE; Notifications; Storage finalization.
- **Payload:** `{report_id|export_id, organization_id, project_id, format, artifact_ref, status}`.

### 2.19 research.experiment.completed
- **Producer:** Research worker.
- **Consumers:** Statistics job; Reproducibility indexer.
- **Payload:** `{research_experiment_id, organization_id, research_project_id, dataset_version_id, model_ref, prompt_version_id, seed, status}`.

### 2.20 retention.purged
- **Producer:** Retention job.
- **Consumers:** Audit; Storage lifecycle.
- **Payload:** `{organization_id, scope, purged_count, window}`.

---

## 3. Consumer Contract

Every consumer must implement:

| Method | Contract |
|--------|----------|
| `handle(event)` | Idempotent; returns ack |
| Dedup | Redis `SET NX` on `event.id` with TTL (e.g., 24h) or DB unique marker |
| Retry | Raise `RetryableError` for transient; `PermanentError` → DLQ + alert |
| Ordering | Use `aggregate_id` partition when order matters (e.g., run_started < progress < completed) |
| Observability | Emit OTel span; expose `consumer_lag`, `processed_total`, `failed_total` metrics |
| Backpressure | Bound concurrency; Redis list length monitored |

## 4. Outbox Relay Contract

- Batch SELECT `outbox_events WHERE processed_at IS NULL ORDER BY created_at LIMIT 100`.
- Publish each to Redis pub/sub (`events`) and/or enqueue Arq job by `event_type` mapping.
- Mark `processed_at` in the same transaction as dispatch (or per-event with idempotent publish).
- Sweep: re-publish events with `attempts < 5`; escalate to DLQ beyond.
- Index: `(processed_at, created_at)`.

## 5. Ordering Guarantees

| Requirement | Guarantee |
|-------------|-----------|
| Per aggregate | `evaluation.*` events ordered by `occurred_at`; consumers may buffer out-of-order `progress` (display only) |
| Global | None (not required) |
| Strict FSM transitions | Enforced in the **writer** (`evaluation_runs.status` state machine), not by event ordering — events are projections |
| CI callback | `evaluation.completed`/`evaluation.failed`/`quality_gate.violated` delivered **at least once**; CI polls as fallback (AC-CICD-002) |

## 6. Retry Policy Summary (§58)

| Class | Examples | Action |
|-------|----------|--------|
| Transient | Redis/DB timeout, provider 5xx/429, email/webhook 5xx | Retry w/ exponential backoff (max 5, configurable) |
| Permanent | Validation, immutable-state violation, malformed payload | Fail immediately → DLQ + `SERVER_ERROR`/`JOB_FAILED` |
| Never | Cancelled jobs | Not retried; terminal state |

## 7. Event → Table Side-Effect Map

| Event | Side-effect tables |
|-------|--------------------|
| evaluation.run_started/completed/failed | evaluation_runs (status, metrics, error) |
| test.results.persisted | test_results |
| alert.fired | alerts + notifications |
| notification.requested | notifications |
| trace.ingested | traces + trace_events + metrics_samples |
| report.generated | reports (artifact_ref) |
| retention.purged | audit_logs (record) |

## 8. PRD Traceability (EVENT)

| PRD requirement | Contract |
|-----------------|----------|
| §56 async pipeline (API→job→queue→workers→results) | §2.8–§2.11 + outbox relay |
| §57 partial failure handling / cancellation | §2.10/§2.11 + retry §6 |
| §58 transient vs permanent retry | §6 |
| §43 alert channels | §2.15 → notification pipeline |
| §85 notifications (eval complete/fail, regression, thresholds, safety) | §2.7/§2.10/§2.11/§2.13/§2.14 |
| §88–§89 job survival / partial results | outbox + idempotent consumers |
| §42 observability | §2.16 trace.ingested |
| AC-CICD-002/003 (result to CI, non-zero exit) | §2.10/§2.14 + webhook contract |
