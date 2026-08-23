# System Architecture — AIREX

**Status:** Architecture design (no implementation)
**Inputs:** PRD V1.0, [`docs/PRD_ANALYSIS/*`](../PRD_ANALYSIS/README.md), acceptance criteria, business rules, user journeys.
**Architecture principle:** Zero-cost / local-first for development; paid-provider adapters designed but not required.

---

## 1. Design Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| P1 | **Local-first, zero-cost by default** | Every component must run fully on a developer laptop (Docker Compose) with free software: PostgreSQL, Redis, MinIO, MailHog, Ollama. Paid providers (OpenAI/Anthropic/Gemini/AWS/SES) are behind adapters and never required for development. |
| P2 | **Modular monolith backend, extracted later** | FastAPI modular monolith with a domain-package layout so modules can be split into services (workers, ingestion) without a rewrite. Matches PRD §108 phased delivery. |
| P3 | **Async by default for heavy work** | Evaluation, test generation, reports, RCA, research stats, alert evaluation run as background jobs (PRD §56–§57). API stays responsive (P95 < 500 ms, §87). |
| P4 | **Tenancy enforced at the data layer** | Every query is scoped by `organization_id`; row-level isolation is enforced by the ORM repository layer, not just middleware (AC-SEC-001, AC-AUTH-005). |
| P5 | **Immutability & versioning are data-model invariants** | Datasets, prompts, pricing configs, experiments, and generated tests are versioned and immutable post-freeze (FR-DATASET-008..010, FR-EXPERIMENT-002, FR-COST-002, FR-VERSION-001). |
| P6 | **Everything observable** | OpenTelemetry traces/metrics on API, workers, gateway, queue; Prometheus/Grafana dashboards (PRD §64). |
| P7 | **Provider abstraction everywhere** | Model calls, email, object storage, and LLM judge go through narrow ports so paid services are swappable with local equivalents. |

---

## 2. System Context Diagram

```
                     ┌──────────────────────────────┐
                     │        Human Users           │
                     │  (AI/ML/MLOps/QA/Research/   │
                     │   Engineering Managers)      │
                     └──────────────┬───────────────┘
                                    │ HTTPS (Browser)
                                    ▼
                     ┌──────────────────────────────┐
                     │        Next.js Web App       │
                     │  (SSR pages per PRD §68)     │
                     └──────────────┬───────────────┘
                                    │ HTTP /api/v1 (JSON)
                                    ▼
┌──────────────┐   CI/CD Trigger   ┌──────────────────────────────┐
│ GitHub        │◄─────────────────│      FastAPI API Server      │
│ Actions / CI  │   (API key)      │  auth · tenancy · orchestration│
└──────────────┘                  └───────┬──────────────┬────────┘
                                          │              │ REST + events
                                          ▼              ▼
                              ┌─────────────────┐  ┌─────────────────┐
                              │  PostgreSQL     │  │  Redis          │
                              │  (+pgvector)    │  │  queue/cache/   │
                              │  (source of     │  │  locks/rate-limit│
                              │   truth)        │  │  pubsub         │
                              └────────┬────────┘  └────────┬────────┘
                                       │                     │
                                       ▼                     ▼
                              ┌─────────────────┐  ┌─────────────────┐
                              │  Arq Workers    │◄─┤  Jobs           │
                              │  (evaluation,   │  │  (enqueued)     │
                              │   test-gen,     │  └─────────────────┘
                              │   reports,      │
                              │   alerts, RCA,  │
                              │   research)     │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌──────────────────────────────┐
                              │         Model Gateway         │
                              │   (provider adapters)        │
                              └───────┬──────────┬───────────┘
                                      ▼          ▼          ▼
                              ┌──────────┐ ┌──────────┐ ┌──────────┐
                              │ OpenAI    │ │ Anthropic│ │ Gemini   │
                              │ (paid opt)│ │ (paid opt)│ │(paid opt)│
                              └──────────┘ └──────────┘ └──────────┘
                                      ▼          ▼          ▼
                              ┌──────────┐ ┌──────────┐ ┌──────────┐
                              │ Ollama    │ │ HF/local │ │ (RAG)    │
                              │ (local,   │ │ (opt)    │ │ pgvector │
                              │  free)    │ └──────────┘ └──────────┘
                              └──────────┘
```

Supporting services:

```
 ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐
 │ MinIO/S3   │  │ MailHog/   │  │ Prometheus │  │ Grafana              │
 │ (storage)  │  │ SES (mail) │  │ (metrics)  │  │ (dashboards)         │
 └────────────┘  └────────────┘  └────────────┘  └──────────────────────┘
                                   OpenTelemetry Collector (traces)
```

---

## 3. Component Catalog

| Component | Tech (zero-cost default → prod option) | Responsibility | PRD modules owned |
|-----------|----------------------------------------|----------------|-------------------|
| **Web App** | Next.js (App Router), React, TypeScript, Tailwind, Recharts | UI, SSR, dashboards, charts, forms, human review | 9, 10, 12, 13, 17, 19, 20, 21, 23, 24, 25, 26, 27, 28 (presentation) |
| **API Server** | FastAPI, Pydantic, SQLAlchemy (async), Alembic | REST API, auth, tenancy, RBAC, sync CRUD orchestration, job dispatch, health | 1–6, 14, 15, 16, 22, 23, 26, 27, 28 (server) |
| **Workers** | Arq (Redis broker), Python | Async execution: evaluation runs, evaluators, test generation, report/export, regression, RCA, recommendations, research stats, alert evaluation, notification dispatch | 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19, 20, 25 (compute) |
| **Model Gateway** | Python library (provider adapters) | Unified inference, telemetry capture, error normalization, retry, timeout, cost accounting | 4, 5, 11, 12, 13 (model path) |
| **PostgreSQL + pgvector** | Postgres 16 + pgvector | Source of truth for all entities; vector store for RAG chunks | All (persistence) |
| **Redis** | Redis 7 | Job queue (Arq), cache, rate-limit counters, distributed locks, temp results, pub/sub events | 18, 23 (async infra) |
| **Object Storage** | MinIO (local) → S3 (prod) | Dataset files, exports, report artifacts, trace payloads | 6, 24, 17 (artifacts) |
| **Mailer** | SMTP adapter; MailHog (local) → SES (prod) | Email verification, password reset, alert/notification email | 1, 18, 28 (email) |
| **Observability** | OpenTelemetry SDK + Collector, Prometheus, Grafana | Metrics, traces, self-observability | 17, 28 (ops) |
| **CI/CD** | GitHub Actions + CLI (`airex`) | Trigger evaluations, quality gate, exit codes | 21, 22, 23 |

> The 28 PRD modules (PRD §8) are **owned** by these components; a full module → component mapping is in §5 and the coverage matrix in [`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md).

---

## 4. Logical Layers

```
┌──────────────────────────────────────────────────────────────┐
│ PRESENTATION      Next.js pages + client components           │
├──────────────────────────────────────────────────────────────┤
│ API LAYER         FastAPI routers (per module), middleware    │
├──────────────────────────────────────────────────────────────┤
│ APPLICATION       Service layer: use-cases, orchestration,    │
│                   job dispatch, event emission                │
├──────────────────────────────────────────────────────────────┤
│ DOMAIN            Evaluators, scoring, regression, RCA,       │
│                   test generator, stats, model gateway ports  │
├──────────────────────────────────────────────────────────────┤
│ PERSISTENCE       SQLAlchemy repositories (tenant-scoped),    │
│                   pgvector, Redis, object storage, audit      │
└──────────────────────────────────────────────────────────────┘
```

Dependency rule: outer layers depend inward; domain depends on no framework. FastAPI/SQLAlchemy stay in the outer two layers. This keeps the evaluation engine (the core, PRD §90 targets ≥90% coverage) framework-free and unit-testable.

---

## 5. Module → Component Ownership

| # | PRD Module (§8) | Primary component | Supporting |
|---|-----------------|-------------------|------------|
| 1 | Authentication | API Server (auth service) | Mailer, Postgres, Redis (sessions/rate limit) |
| 2 | Organization Management | API Server (org service) | Postgres, Audit |
| 3 | Project Management | API Server (project service) | Postgres |
| 4 | AI Provider Management | API Server + Model Gateway | Postgres (encrypted keys) |
| 5 | Model Gateway | Model Gateway library | Redis (locks/rate limit), Postgres (telemetry) |
| 6 | Dataset Management | API Server (ingest) + Workers (parse) | Postgres, Object Storage, Redis (temp) |
| 7 | Evaluation Engine | Workers (evaluators) | Model Gateway, Postgres, Redis (jobs) |
| 8 | AI Test Generator | Workers | Model Gateway, Postgres, Redis |
| 9 | RAG Evaluation Engine | Workers | pgvector, Model Gateway |
| 10 | Safety Evaluation Engine | Workers | Model Gateway |
| 11 | Hallucination Detection | Workers | Model Gateway |
| 12 | Performance Evaluation | Workers + API Server (ingest) | Postgres (metrics) |
| 13 | Cost Analytics | Workers + API Server | Postgres (pricing configs) |
| 14 | Experiment Management | API Server + Workers | Postgres |
| 15 | Prompt Management | API Server | Postgres |
| 16 | Regression Testing | Workers | Postgres |
| 17 | Production Observability | API Server (ingest) + Workers (aggregate) + Web App | Postgres, Redis, Object Storage |
| 18 | Alerting | Workers (alert evaluator) + Notifier | Redis, Mailer, Webhook, In-app |
| 19 | Root Cause Analysis | Workers | Postgres, Model Gateway |
| 20 | Recommendation Engine | Workers | Postgres, Model Gateway |
| 21 | CI/CD Integration | API Server (trigger) + CLI | Object Storage (artifacts) |
| 22 | CLI | CLI (Python, `airex`) | API Server |
| 23 | API | API Server | OpenAPI |
| 24 | Reporting | Workers | Object Storage, Postgres |
| 25 | Research Workspace | API Server + Workers (stats) | Postgres |
| 26 | Audit Logs | API Server middleware + Workers | Postgres (append-only) |
| 27 | Security | Cross-cutting (authz middleware, secrets, redaction) | All |
| 28 | Administration | API Server (admin service) | Postgres |

---

## 6. Request Flows

### 6.1 Synchronous (API P95 < 500 ms, §87)
Dashboard load, project/dataset/model/prompt CRUD, list queries, auth, alerts listing, report metadata, health checks. API server reads Postgres/Redis directly.

### 6.2 Asynchronous (jobs, §56)
```
Client/CI → POST /evaluations/{id}/run
  → API validates (tenant, versions pinned, not archived, rate limit)
  → creates evaluation_runs row (status=QUEUED)
  → enqueues job "run_evaluation" to Redis via Arq
  → returns 202 { job_id, status }
Workers → dequeue → RUNNING → per-test execution via Model Gateway
  → partial results persisted per test (test_results)
  → on completion: compute metrics, score, regression, RCA, alerts, notify
  → status=COMPLETED/FAILED
Client → GET /evaluations/{id} polls status (or SSE/WebSocket live)
```

### 6.3 Real-time (observability, traces)
Trace ingestion writes to Postgres (`traces`, `trace_events`) via the API server/gateway hook; heavy aggregation runs as periodic jobs; dashboard queries recent data from Postgres (Redis cache for hot metrics).

### 6.4 Alert evaluation
Periodic worker (cron-style, e.g., every minute) evaluates `alert_rules` against windowed metrics in Redis/Postgres; fires `alert` records + notification events (in-app, email, webhook).

---

## 7. Tenancy Model

- **Tenant = organization** (PRD §10). All tenant-owned rows carry `organization_id`.
- Repository layer injects `organization_id` and `project_id` scoping into every query → prevents cross-tenant leaks even if a controller forgets (AC-SEC-001, AC-SEC-002).
- PostgreSQL RLS (row-level security) as a defense-in-depth second barrier, enabled per tenant table.
- Users may belong to multiple organizations (`organization_members` with per-org role).
- Cross-tenant access tests (AC-SEC-001..005) map to the tenancy middleware + RLS + repository scope.

---

## 8. Zero-Cost Local Development Topology (Docker Compose)

```
app: Next.js (dev) ──► api: FastAPI (uvicorn --reload)
                       │
postgres:16 (+pgvector)  redis:7  minio (S3-compat)  mailhog (SMTP sink)
                                │
worker: arq worker (hot-reload)  ollama (local models, OpenAI-compatible)
                                │
otel-collector ─► prometheus ─► grafana (optional, dev profile)
```

- All services are free/open-source. No external account required to run the full platform locally.
- Provider adapters are exercised against **Ollama** (free) by default; OpenAI/Anthropic/Gemini keys are optional and only enable their adapters.
- Email verification/notifications route to **MailHog** locally.

---

## 9. Architecture Constraints from the PRD (accepted)

| Constraint | Source | Architectural consequence |
|-----------|--------|---------------------------|
| API P95 < 500 ms (non-AI) | §87 | Sync path keeps heavy work async; dashboard queries cached |
| Dashboard load < 3 s | §87 | SSR + targeted client fetch; metrics aggregated |
| Jobs survive restarts; partial results kept | §88–§89 | Durable job queue + per-test result persistence |
| Experiments immutable after completion | §34 | Versioned, append-only result tables |
| Version pinning on every run | §78 | FKs to version tables, not live rows |
| 99.5% availability (MVP) | §88 | Health checks, redundant app replicas, managed DB |
| Multi-tenant isolation | §10, §93 | Tenant-scoped repositories + RLS |
| Coverage targets | §91 | Framework-free evaluator domain → high testability |
