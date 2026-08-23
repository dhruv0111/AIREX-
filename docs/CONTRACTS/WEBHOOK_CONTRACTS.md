# Webhook Contracts — AIREX

Two outbound webhook surfaces mandated/implied by the PRD:

1. **Alert webhooks** (PRD §43 — channel "webhook") — push alert/notification events to customer-configured endpoints.
2. **CI result webhook** (implied by PRD §38/§40 AC-CICD-001..005) — return evaluation/quality-gate results to the customer's CI pipeline.

Both use the same delivery contract: **HMAC-SHA256 signature, at-least-once delivery, exponential-backoff retry, dead-letter on permanent failure** (resolves AMB-API-006).

---

## 1. Common Delivery Contract

### 1.1 Headers
| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |
| `X-Airex-Event` | event type (e.g., `alert.fired`, `evaluation.completed`, `quality_gate.violated`) |
| `X-Airex-Webhook-Id` | UUID v7 — unique per delivery attempt (idempotency for receivers) |
| `X-Airex-Event-Id` | original event id (dedup across retries) |
| `X-Airex-Timestamp` | ISO 8601 UTC of request |
| `X-Airex-Signature` | `sha256=<hex>` HMAC of the raw body using the org's webhook secret (see §1.2) |
| `X-Airex-Delivery` | `initial|retry` |

### 1.2 Signature
```
signature = HMAC_SHA256(secret, "<timestamp>.<raw_body>")
Header: X-Airex-Signature: sha256=<hex(signature)>
```
- Receiver MUST verify: (a) timestamp within ±5 min (replay protection), (b) signature matches, (c) `X-Airex-Webhook-Id` not already processed (idempotency).
- Secret: per-org webhook secret, provided at webhook configuration time (Admin), revocable/rotatable.

### 1.3 Delivery & Retry
| Property | Contract |
|----------|----------|
| Timeout | 10 s connect, 30 s response |
| Success | HTTP 2xx |
| Retry | Transient failures (timeout, 5xx, 429) → exponential backoff: 1m, 5m, 30m, 2h, 6h (max 5 attempts, configurable) |
| Permanent | 4xx → dead-letter (no retry), recorded + admin alert |
| Dead-letter | `webhook_deliveries` rows with status `dead_lettered`; visible in admin; manual resend endpoint |
| Ordering | Per webhook: FIFO within a 5-min window; no strict global ordering |
| Idempotency | Receiver dedupes on `X-Airex-Webhook-Id` / `X-Airex-Event-Id` |

### 1.4 Webhook Endpoint Configuration (Admin)
```
POST /api/v1/organizations/{id}/webhooks
{
  "url": "https://customer.example.com/hooks/airex",
  "events": ["alert.fired", "quality_gate.violated", "evaluation.completed"],
  "secret": "<generated once, shown once>",
  "enabled": true
}
```
- `GET/DELETE/PATCH /api/v1/organizations/{id}/webhooks/{webhook_id}`
- Delivery ledger: `webhook_deliveries (id, webhook_id, event_id, url, status, attempts, next_attempt_at, last_error, created_at)`.

---

## 2. Alert Webhook Payload (PRD §43)

Triggered by `alert.fired` event; channel = `webhook`.

```json
{
  "schema_version": 1,
  "event_id": "01JXYZ...",
  "event_type": "alert.fired",
  "occurred_at": "2026-08-21T19:03:00.000Z",
  "organization_id": 42,
  "project_id": 7,
  "project_name": "Enterprise AI Assistant",
  "alert": {
    "id": "alrt_...",
    "rule_id": "r_...",
    "type": "latency",              // accuracy|hallucination|latency|error|cost|safety|model_failure (§43)
    "severity": "critical",         // info|warning|critical (§44)
    "metric": "p95_latency_ms",
    "value": 3400,
    "threshold": 3000,
    "operator": "gt",
    "duration_seconds": 600,
    "status": "firing"              // firing|resolved|acknowledged
  },
  "links": {
    "project": "https://airex.example.com/projects/7/alerts"
  }
}
```

---

## 3. CI Result Webhook (PRD §38, §40)

Triggered by `evaluation.completed`, `evaluation.failed`, or `quality_gate.violated` when `triggered_by=ci`. Purpose: return result to the pipeline; combined with polling fallback and CLI exit codes (AC-CICD-001..005).

```json
{
  "schema_version": 1,
  "event_id": "01JXYZ...",
  "event_type": "evaluation.completed",
  "occurred_at": "2026-08-21T19:03:00.000Z",
  "organization_id": 42,
  "project_id": 7,
  "pipeline": {
    "provider": "github-actions",
    "run_id": "1234567890",
    "workflow": "ci.yml",
    "ref": "refs/heads/main",
    "sha": "abc123...",
    "callback_url": "https://customer.example.com/cicd/callback"   // optional
  },
  "evaluation": {
    "run_id": "evrun_...",
    "evaluation_id": "eval_...",
    "status": "COMPLETED",
    "dataset_version_id": 3,          // pinned (AC-CICD-005)
    "dataset_version_no": 1,
    "model_ref": "gpt-4o",
    "prompt_version_id": 7,
    "metrics": {"accuracy": 0.87, "hallucination": 0.08, "safety": 0.97,
                "p95_latency_ms": 2100, "cost_per_request": 0.019},
    "score": 83.1,
    "regression_status": "regression_detected",
    "quality_gate": {
      "status": "fail",               // pass|fail (AC-CICD-003/004)
      "thresholds": {"accuracy_min": 0.90, "hallucination_max": 0.05,
                     "safety_min": 0.95, "p95_latency_max_ms": 3000,
                     "cost_per_request_max": 0.03},       // §39 example
      "violations": [
        {"metric": "accuracy", "expected_min": 0.90, "actual": 0.87},
        {"metric": "hallucination", "expected_max": 0.05, "actual": 0.08}
      ]
    }
  },
  "links": {
    "results": "https://airex.example.com/api/v1/evaluations/eval_/results",
    "report": "https://airex.example.com/api/v1/reports/rpt_"
  }
}
```

**Exit-code contract (AC-CICD-003/004):**
- `quality_gate.status = pass` → pipeline success (exit 0).
- `quality_gate.status = fail` → pipeline failure (non-zero exit) → `BUILD FAILED` (§39).
- `evaluation.failed` (job failure) → non-zero exit.

---

## 4. Webhook Registry (database)

| Table | Purpose |
|-------|---------|
| `webhooks (id, organization_id, url, events[], secret_hash, secret_encrypted, enabled, created_by, created_at, updated_at, deleted_at)` | Endpoint config (Admin) |
| `webhook_deliveries (id, webhook_id, event_id, url, status, attempts, next_attempt_at, last_error, created_at, completed_at)` | Delivery ledger (retry/DLQ) |

---

## 5. Security Notes

- Signature verification is **mandatory** guidance to receivers (documented in API docs).
- Secrets stored hashed + encrypted; shown once at creation (AC-SEC-003 pattern).
- Payloads contain no provider API keys, no user credentials, no unmasked PII (redaction applied per §60 before webhook emission).
- Webhook URLs allowlisted to `https` (except local dev allowlist).

---

## 6. PRD Traceability (WEBHOOK)

| PRD requirement | Contract |
|-----------------|----------|
| §43 channels include webhook | §2 alert payload ✅ |
| §44 alert rule attributes | alert payload fields ✅ |
| §38 CI/CD integration | §3 CI webhook ✅ |
| §40 AC-CICD-001..005 (trigger, result return, exit codes, dataset pin) | §3 ✅ |
| §39 quality gate → BUILD FAILED | §3 exit-code contract ✅ |
| §63 consistent errors | delivery errors use standard envelope ✅ |
| §60 privacy (no unmasked sensitive data) | §5 redaction ✅ |
| §93 AC-SEC-003 (no plaintext secrets) | §5 secret handling ✅ |
