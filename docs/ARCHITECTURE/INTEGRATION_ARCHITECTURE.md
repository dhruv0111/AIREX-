# Integration Architecture — AIREX

External integrations (from [`INTEGRATIONS.md`](../PRD_ANALYSIS/INTEGRATIONS.md)) designed as **ports and adapters** so that paid services are swappable with free/local equivalents. Development never requires a paid service. No provider is assumed where the PRD is silent (email, storage, payment, SSO).

---

## 1. Adapter Pattern

```
            ┌────────────────────────────┐
 Application service ──► Port (interface)
            └────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   Adapter A        Adapter B       Adapter C
 (local, free)    (open-source)    (paid provider)
```

Ports used: `ModelGatewayPort`, `StoragePort`, `MailerPort`, `VectorStorePort`, `NotifierPort` (webhook). Selection via config; each adapter isolated and unit-tested against a fake.

---

## 2. AI Model Providers (PRD §12, §67)

| Adapter | Class | Local (default) | Notes |
|---------|-------|-----------------|-------|
| `OllamaAdapter` | FREE | ✅ **default in dev** | OpenAI-compatible local API; exercises the full gateway path without any paid account |
| `OpenAIAdapter` | PAID (optional) | ❌ | Activated only when an API key is configured (AC-MODEL-001..004) |
| `AnthropicAdapter` | PAID (optional) | ❌ | Same |
| `GeminiAdapter` | PAID (optional) | ❌ | Same |
| `HuggingFaceAdapter` | FREE/optional | ✅ optional | Local/self-hosted HF endpoints |
| Open-source "compatible APIs" | FREE/optional | ✅ | Via OpenAI-compatible HTTP (vLLM/Ollama style) — AMB-PROVIDER-001 resolution |

- Gateway normalizes responses (text, latency, tokens, cost), errors (AC-MODEL-002..004), timeouts, retries (§58), provider rate limits, telemetry.
- **AI Judge** (PRD §74) uses the same gateway with a configurable judge model (default local Ollama; paid providers optional) — AMB-JUDGE-001 resolution. Judge settings (model, temperature, prompt version) recorded per judgment for reproducibility.

## 3. Object Storage (PRD §79–§80; datasets/exports/reports/traces)

| Adapter | Class | Notes |
|---------|-------|-------|
| `LocalStorageAdapter` | FREE | Dev filesystem (./data) |
| `MinIOAdapter` | FREE | S3-compatible; recommended local service |
| `S3Adapter` | PAID (prod optional) | AWS S3; same S3 API as MinIO → config swap only |

Port: `put/get/delete/presign`. Presigned URLs for uploads/downloads keep API light; bucket policy + tenant prefix (`{org_id}/{project_id}/...`).

## 4. Email (PRD §9 verification, §43 alerts, §85 notifications)

| Adapter | Class | Notes |
|---------|-------|-------|
| `MailHogAdapter` / SMTP | FREE | Local dev sink (MailHog) — captures all outbound email |
| `SESAdapter` | PAID (prod optional) | AWS SES via SMTP or SDK |
| `SendGridAdapter` (optional) | PAID (optional) | Alternative |

Port: `send(template, to, ctx)`. Templates: email verification, password reset, evaluation complete/failed, regression, threshold, safety (mapped from FR-NOTIFY-001..006).

## 5. CI/CD Integration (PRD §38–§40)

- **Trigger:** CI calls `POST /api/v1/evaluations/{id}/run` (or CLI `airex evaluate run`) authenticated with an **org API key** (AMB-CICD-002 resolution). 
- **Result:** CI polls the run status or receives a completion webhook; **exit code** is non-zero when the quality gate fails (AC-CICD-003) and zero on pass (AC-CICD-004); dataset version pinned in the trigger payload (AC-CICD-005).
- **Deliverable:** a sample GitHub Actions workflow (`deploy/ci/airex-evaluate.yml`) ships with the repo; generic for any CI supporting HTTP + env vars.

## 6. Alert Webhooks (PRD §43)

- Outbound webhook adapter: POSTs a signed payload (HMAC-SHA256, shared secret per org) with retry/backoff and dead-letter (AMB-API-006 resolution).
- Payload: `{event, alert, rule, org_id, project_id, severity, metric, value, threshold, occurred_at, signature}`.

## 7. Vector Database (PRD §54)

| Adapter | Class | Notes |
|---------|-------|-------|
| `PgvectorAdapter` | FREE | **Default**; embeddings in PostgreSQL (HNSW index) |
| `ExternalVectorAdapter` | FREE/PAID (later) | Future external vector DBs behind the same port — AMB-VECTOR-001 resolution |

Embedding generation via gateway (configured embedding model, versioned per project for reproducibility).

## 8. Observability Exports (PRD §64)

- OpenTelemetry Collector → Prometheus + Grafana (FREE). Optional paid (Datadog etc.) behind an OTLP exporter only.
- Out-of-the-box dashboards: API latency, worker latency, queue depth, error rate, DB performance, Redis health, provider health, evaluation throughput.

## 9. Authentication Integration

- **SSO (enterprise, V3 — PRD §98):** designed as an optional `IdentityProviderPort` (OIDC/SAML) — not implemented in MVP; no provider assumed.

## 10. Payment / Billing

- **Platform billing is out of MVP scope** (AMB-BILLING-001 resolution per PRD §96 which omits it). A future `BillingPort` (Stripe etc.) is **not designed** now; only AI inference **cost analytics** (§31) is in scope, computed from versioned pricing configs.

## 11. Integration Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| Ports/adapters | Paid services optional; local parity (P1) | Hard-coded SDKs | More interfaces | Free | Swappable scale profiles | Keys isolated per adapter |
| Ollama default in dev | Full gateway path without paid accounts | Paid keys only | Local model fidelity vs prod | Free | — | No external key handling in dev |
| S3-compatible storage (MinIO→S3) | Free local ↔ prod parity | Custom FS | MinIO vs S3 edge cases | Free→paid(prod) | Native S3 scale | Bucket policies + presigned URLs |
| SMTP/SES mailer | Verification/notifications without vendor lock-in | SendGrid | Deliverability tuning | Free→paid(prod) | Provider-backed | Template hygiene, no secrets in mail |
| HMAC-signed webhooks | Authenticate outbound alert delivery (AMB-API-006) | None/unsigned | Secret mgmt | Free | — | Signature verification |
| API-key CI trigger | CI auth without user sessions (AMB-CICD-002) | OAuth2 machine creds | Key rotation needed | Free | — | Scoped keys, revocation |
| OTel + Prometheus/Grafana | Zero-cost self-observability (§64) | Paid APM | Self-hosted ops | Free | Pull model scales | — |
