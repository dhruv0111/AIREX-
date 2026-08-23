# Event Architecture — AIREX

Event-driven interactions between API server, workers, notifications, alerts, and observability. Uses a **transactional outbox** (reliable) + **Redis pub/sub** (fast fan-out) + **Redis-backed job queue** (Arq). No paid broker required (Kafka is a later option).

---

## 1. Principles

| Principle | Implementation |
|-----------|----------------|
| **Reliability** | Side effects are driven from a transactional outbox: a service writes domain state + an `outbox_events` row in the **same DB transaction**; a relay publishes to Redis pub/sub or enqueues jobs. No lost events (matches §89 partial-result guarantees). |
| **Consistency** | Consumers are idempotent (event `id` dedup via processed markers). |
| **Decoupling** | Producers don't know consumers; new consumers subscribe without producer changes. |
| **At-least-once** | Delivery is at-least-once; consumers dedupe. |
| **Zero-cost** | Redis pub/sub + Arq queue; no Kafka in MVP. |

## 2. Event Flow

```
Service (DB transaction)
   ├─ write aggregate state (e.g., evaluation_run COMPLETED)
   └─ write outbox_events (event_type, payload, aggregate_id)
             │
             ▼
   Outbox relay (worker, periodic + immediate)
             │
     ┌───────┴────────┐
     ▼                ▼
Redis pub/sub      Arq job enqueue
     │                │
     ▼                ▼
 SSE to Web App    Job consumers
 notifications     (evaluation, alert eval,
 email/webhook      aggregation, retention)
```

## 3. Event Catalogue

| Event | Producer | Consumers |
|-------|----------|-----------|
| `user.registered` | Auth service | Mailer (verification email), audit |
| `user.login` | Auth service | Audit, security monitor |
| `organization.member.role_changed` | Org service | Audit, session invalidation |
| `project.created/deleted/archived` | Project service | Audit, index/cache invalidation |
| `api_key.created/deleted` | Admin service | Audit |
| `dataset.version_created` | Dataset service | Cache invalidation, version compare refresh |
| `evaluation.created` | Evaluation service | Metrics, audit |
| `evaluation.run_started` | Worker | SSE, notifications |
| `evaluation.progress` | Worker (throttled) | SSE live dashboards |
| `evaluation.completed` | Worker | Notifications, regression check, quality gate, alert eval, RCA/recommendations, aggregation, cache invalidation, CI result webhook |
| `evaluation.failed` | Worker | Notifications, alerts (model failure), audit |
| `test.results.persisted` | Worker (batch) | Aggregation |
| `test.generation.completed` | Worker | SSE, notifications |
| `regression.detected` | Regression service | Notifications, alerts, dashboard, CI |
| `quality_gate.violated` | Quality gate | CI, notifications, alerts |
| `alert.fired` | Alert evaluator | Notifications (in-app/email/webhook), SSE |
| `trace.ingested` | Ingest path | Aggregation, anomaly detection (later) |
| `notification.requested` | Any | Notifier worker (dedupe, channel routing) |
| `report.generated` | Report worker | SSE, artifact links |
| `research.experiment.completed` | Research worker | Statistics job, reproducibility metadata |
| `retention.purged` | Retention job | Audit |

## 4. Async Job Lifecycle (evaluation — PRD §56–§57)

```
POST /run ──► evaluation_runs(status=QUEUED) ──► enqueue job
Job: run_evaluation
  1. claim (Redis lock per org/project) → RUNNING
  2. fan out test execution (bounded concurrency)
     ├─ each test: gateway call + evaluators
     ├─ persist test_results immediately (partial safety, §89)
     └─ progress events (throttled)
  3. aggregate metrics → score → regression → gate → RCA → recommendations
  4. status=COMPLETED | FAILED; emit evaluation.completed/failed
Retry policy: transient retries (Arq, backoff, max configurable §58);
permanent failures → FAILED with normalized error.
Cancellation: revoke pending tasks; in-flight test finishes/aborts gracefully.
```

## 5. Notification Pipeline (PRD §43, §85)

```
event (evaluation.completed, regression.detected, alert.fired, …)
  → notification.requested (dedup key: event+org+user)
  → Notifier worker
       ├─ in-app: insert notifications row → SSE push
       ├─ email: Mailer (MailHog local / SES prod) with per-user prefs (AMB-NOTIF-001 resolution)
       └─ webhook: POST to configured URL (HMAC-signed payload, retry w/ backoff, AMB-API-006 resolution)
```

## 6. Alert Evaluation (PRD §43–§44)

- Periodic worker (every minute) reads enabled `alert_rules` and evaluates against windowed metrics (Redis + metric_aggregates).
- Rule semantics: `IF metric OP threshold FOR duration THEN alert`; respects severity, cooldown, enabled flag (BR-ALERT-001..003).
- Fires `alert.fired` → notification pipeline; unresolved alerts surface on dashboards (§50).
- Rate-limited to avoid alert storms; dedup on (rule, org, window).

## 7. Observability Data Path

- Trace ingestion (API/gateway hook) writes `traces`/`trace_events` (respecting privacy toggles §60); emits `trace.ingested` for aggregation.
- Aggregation job rolls up `metrics_samples` → `metric_aggregates` (P50/P95/P99, error rate, RPS) for dashboards; Redis caches hot windows (30 s–5 min).
- Alert evaluator and dashboards read aggregates, not raw events → bounded load.

## 8. SSE / Live Updates

- `GET /api/v1/stream` subscribes to Redis pub/sub (`events:{org_id}`); server pushes typed JSON (evaluation status, alert, progress).
- Cookie-authenticated; connection-scoped filter by org/project.

## 9. Failure Handling & Reliability (PRD §88–§89)

| Failure | Behavior |
|---------|----------|
| Consumer crash mid-event | Outbox relay re-publishes; consumers idempotent (dedupe by event id) |
| Worker crash mid-evaluation | Per-test results already persisted; job re-enqueued (idempotent run key) and continues |
| Redis unavailable | API degrades (cache misses, jobs not enqueued); health `/ready` fails; recovery replays outbox |
| Webhook target down | Retry with exponential backoff + dead-letter after N; status recorded |
| Email provider down | In-app + outbox retained; retry; webhook alternative |

## 10. Outbox Design

```
outbox_events (
  id UUID PK, aggregate_type, aggregate_id,
  event_type, payload JSONB,
  created_at, processed_at NULL, attempts INT
)
```
Relay: batched SELECT WHERE processed_at IS NULL → publish → mark processed (transactional per batch). Periodic sweep for stuck events (visibility timeout). Index on `(processed_at, created_at)`.

## 11. Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| Transactional outbox | Reliable side effects with DB consistency (§89) | Direct pub/sub, CDC | Extra table + relay | Free | Horizontal relays | Event integrity |
| Redis pub/sub + Arq | Zero-cost, matches §55/§67 | Kafka, SQS (paid) | Pub/sub not durable (outbox compensates) | Free | Horizontal consumers | Auth at broker (dev local) |
| Idempotent consumers | At-least-once delivery safety | Exactly-once (harder) | Dedup logic | Free | — | Prevents duplicate effects |
| Event-driven alerts/notifications | Decouple alert eval from API | Polling | Async latency (≤1 min) | Free | Scales | — |
| SSE fan-out | Live dashboards | WebSocket | One-way | Free | Redis fan-out | Cookie-auth |
