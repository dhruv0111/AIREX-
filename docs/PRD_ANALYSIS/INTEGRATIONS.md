# Integrations — AIREX

Every external integration mentioned (or implied) by the PRD V1.0, classified as **FREE / PAID / OPTIONAL / REQUIRED**. The PRD names specific providers for AI models and tooling but does **not** name providers for email, storage, payment, or SSO — those are marked **PROVIDER NOT DEFINED** (no provider is assumed).

Classification legend:
- **REQUIRED** = the PRD requires this capability in MVP (§96) or treats it as core.
- **OPTIONAL** = explicitly optional or deferred (V2/V3 per §97–§98, or "later").
- **FREE** / **PAID** = licensing/business model of the external service.
- **PROVIDER NOT DEFINED** = capability required but no vendor named.

---

## 1. AI Model Provider Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **OpenAI** | Primary model provider | **REQUIRED** · PAID | §12, §67 | Adapter required |
| **Anthropic** | Primary model provider | **REQUIRED** · PAID | §12, §67 | Adapter required |
| **Google Gemini** | Primary model provider | **REQUIRED** · PAID | §12, §67 | Adapter required |
| **Open-source models (compatible APIs)** | Model provider | **OPTIONAL** · FREE/PAID | §12 | "through compatible APIs" |
| **Local models** | Model provider (self-hosted) | **OPTIONAL** · FREE | §12 | e.g., Ollama/vLLM-style — not named |
| **Hugging Face** | AI provider in tech stack | **OPTIONAL** · FREE | §67 | Tech-stack mention only |
| **AI Judge LLM** | LLM-as-evaluator (§74) | **REQUIRED (capability)** · provider NOT DEFINED | §74 | Which model/provider is NS — see AMB-JUDGE-001 |

> The Model Gateway abstraction (§13) is the required integration point for all model providers.

---

## 2. Infrastructure & Platform Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **PostgreSQL** | Primary database | **REQUIRED** · FREE | §53 | Recommended |
| **pgvector** | Vector storage | **REQUIRED (initial)** · FREE | §54, §67 | "initially" |
| **External vector databases** | Vector storage (later) | **OPTIONAL** · provider NOT DEFINED | §54 | "optional external vector databases later" |
| **Redis** | Cache/queue/locks/rate-limit | **REQUIRED** · FREE | §55 | Evaluation jobs, rate limiting, temp results, distributed locks, task queues |
| **Celery/RQ/Arq** | Worker/queue framework | **REQUIRED (initial)** · FREE | §67 | "initially" — later may change |
| **Docker** | Containerization | **REQUIRED** · FREE | §67 | |
| **Kubernetes** | Orchestration | **OPTIONAL (V2)** · FREE | §97 | V2 scope |
| **AWS** | Cloud platform | **REQUIRED (target)** · PAID | §67 | Named cloud |

---

## 3. Observability & Monitoring Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **OpenTelemetry** | Telemetry/export | **REQUIRED** · FREE | §64, §67 | Recommended |
| **Prometheus** | Metrics collection | **REQUIRED** · FREE | §64, §67 | Recommended |
| **Grafana** | Dashboards | **REQUIRED** · FREE | §64, §67 | Recommended |

---

## 4. CI/CD Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **GitHub Actions** | CI/CD trigger & quality gate | **REQUIRED** · FREE | §38, §67 | Named in tech stack |
| **Generic CI trigger API/CLI** | Any CI can trigger evaluation (AC-CICD-001) | **REQUIRED (capability)** · — | §38, §40 | Other CI systems not excluded; mechanism NS — see AMB-CICD-002 |

---

## 5. Communication & Alerting Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **Email (alerts)** | Alert channel | **REQUIRED (capability)** · PROVIDER NOT DEFINED | §43 | Provider (e.g., SES/SendGrid/Postmark) not named — AMB-EMAIL-001 |
| **Email (verification/notifications)** | Email verification (§9), notifications (§85) | **REQUIRED (capability)** · PROVIDER NOT DEFINED | §9, §85 | Provider not named — AMB-EMAIL-001 |
| **Webhook (alerts)** | Outbound alert delivery | **OPTIONAL** · — | §43 | Payload format NS — AMB-API-006 |
| **In-app notifications** | Alert/notification channel | **REQUIRED** · internal | §43, §85 | Internal feature, not an external integration |

---

## 6. Authentication Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **Enterprise SSO** | SSO login | **OPTIONAL (V3)** · provider NOT DEFINED | §98 | V3 scope; provider NS |
| **OAuth** | General auth mention | **NOT DEFINED as feature** | — | The word "OAuth" appears only in the master-instruction taxonomy; the PRD does not require OAuth login in V1. Not assumed. |

---

## 7. Financial / Billing Integrations

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **Payment processor** | Platform subscription billing | **NOT DEFINED** | — | PRD defines AI **cost analytics** (§31) but no platform billing/subscription module — AMB-BILLING-001 |

---

## 8. Object Storage & Data

| Integration | Purpose | Class | PRD Source | Notes |
|-------------|---------|-------|-----------|-------|
| **Object storage (e.g., S3)** | Dataset artifacts, exports, traces, reports | **NOT DEFINED** | — | Not mentioned; large-file storage strategy NS — AMB-STORAGE-001 |

---

## 9. Summary Table

| # | Integration | Classification |
|---|-------------|----------------|
| 1 | OpenAI | REQUIRED · PAID |
| 2 | Anthropic | REQUIRED · PAID |
| 3 | Google Gemini | REQUIRED · PAID |
| 4 | Open-source models (compatible APIs) | OPTIONAL · FREE/PAID |
| 5 | Local models | OPTIONAL · FREE |
| 6 | Hugging Face | OPTIONAL · FREE |
| 7 | AI Judge LLM | REQUIRED capability · provider NOT DEFINED |
| 8 | PostgreSQL | REQUIRED · FREE |
| 9 | pgvector | REQUIRED (initial) · FREE |
| 10 | External vector DB | OPTIONAL · provider NOT DEFINED |
| 11 | Redis | REQUIRED · FREE |
| 12 | Celery/RQ/Arq | REQUIRED (initial) · FREE |
| 13 | Docker | REQUIRED · FREE |
| 14 | Kubernetes | OPTIONAL (V2) · FREE |
| 15 | AWS | REQUIRED (target) · PAID |
| 16 | OpenTelemetry | REQUIRED · FREE |
| 17 | Prometheus | REQUIRED · FREE |
| 18 | Grafana | REQUIRED · FREE |
| 19 | GitHub Actions | REQUIRED · FREE |
| 20 | Generic CI trigger | REQUIRED capability · mechanism NS |
| 21 | Email (alerts/verification/notifications) | REQUIRED capability · provider NOT DEFINED |
| 22 | Webhook (alerts) | OPTIONAL |
| 23 | Enterprise SSO | OPTIONAL (V3) · provider NOT DEFINED |
| 24 | Payment processor | NOT DEFINED |
| 25 | Object storage | NOT DEFINED |

---

## 10. Integration Gaps (→ AMBIGUITY_REGISTER)

| Ambiguity | Description |
|-----------|-------------|
| AMB-EMAIL-001 | Email provider for verification/alerts/notifications not named |
| AMB-STORAGE-001 | Object storage for datasets/exports/reports not addressed |
| AMB-JUDGE-001 | AI Judge provider/cost/keys undefined |
| AMB-BILLING-001 | No payment/subscription integration |
| AMB-API-006 | Alert webhook payload contract undefined |
| AMB-CICD-002 | CI authentication mechanism undefined |
