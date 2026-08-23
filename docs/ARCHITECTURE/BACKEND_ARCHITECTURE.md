# Backend Architecture — AIREX

**Stack (PRD §67):** Python, FastAPI, Pydantic, SQLAlchemy (async), Alembic, Arq (Redis-based workers). All free/open-source.

**Shape:** Modular monolith (API server) + separate worker process sharing a common domain library. This satisfies PRD §108 (phased, always-working) while allowing later extraction of evaluation/ingestion into services.

---

## 1. Repository Layout

```
backend/
├── pyproject.toml            # deps: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg,
│                             #  pydantic-settings, alembic, arq, redis, httpx,
│                             #  cryptography(Fernet), argon2-cffi, python-jose|pyjwt,
│                             #  opentelemetry-*, prometheus-client, jinja2, weasyprint,
│                             #  ollama|openai|anthropic sdks, pandas, scipy
├── airex/
│   ├── main.py               # FastAPI app factory (routers, middleware, lifespan)
│   ├── config.py             # pydantic-settings (env-driven), per-env profiles
│   ├── core/                 # domain-agnostic infra
│   │   ├── db.py             # async engine/session factory
│   │   ├── redis.py          # cache/queue/locks clients
│   │   ├── storage.py        # object storage port + local/MinIO/S3 impl
│   │   ├── mailer.py         # SMTP port + MailHog/SES impl
│   │   ├── events.py         # outbox + event bus
│   │   ├── errors.py         # standardized error model (§63)
│   │   ├── auth.py           # password hashing, JWT, verification tokens
│   │   ├── rbac.py           # role/capability checks
│   │   ├── tenancy.py        # tenant-scoping middleware + repo helpers
│   │   ├── ratelimit.py      # Redis sliding-window rate limiter
│   │   ├── audit.py          # append-only audit logger
│   │   ├── redact.py         # PII masking/redaction pipeline (§60)
│   │   ├── tracing.py        # OpenTelemetry init
│   │   └── jobs.py           # Arq job registry + enqueue helpers
│   ├── models/               # SQLAlchemy ORM models (all tenant-scoped)
│   ├── schemas/              # Pydantic request/response schemas
│   ├── repositories/         # tenant-scoped data access (per aggregate)
│   ├── services/             # use-case orchestration per module
│   │   ├── auth_service.py
│   │   ├── org_service.py
│   │   ├── project_service.py
│   │   ├── provider_service.py
│   │   ├── dataset_service.py
│   │   ├── prompt_service.py
│   │   ├── experiment_service.py
│   │   ├── observability_service.py
│   │   ├── research_service.py
│   │   └── admin_service.py
│   ├── api/                  # FastAPI routers (thin)
│   │   ├── v1/…              # one router per resource (§51 + extensions)
│   │   └── health.py         # /health /ready /live
│   ├── domain/               # FRAMEWORK-FREE core (target ≥90% coverage, §91)
│   │   ├── evaluators/       # exact_match, semantic, correctness, hallucination,
│   │   │                     #  rag_retrieval, rag_generation, safety, bias,
│   │   │                     #  injection, leakage, format, consistency, latency,
│   │   │                     #  cost, regression (each: analyze() -> Verdict)
│   │   ├── scoring.py        # AI Reliability Score (§83, AC-SCORE-001..004)
│   │   ├── regression.py     # baseline vs new comparison, thresholds (§36–§37)
│   │   ├── quality_gate.py   # gate evaluation (§39, AC-CICD-003/004)
│   │   ├── test_generator/   # category generators (8 categories, §26)
│   │   ├── rca.py            # failure classification + likely-cause (§25, §45)
│   │   ├── recommend.py      # recommendation candidates (§46)
│   │   ├── stats.py          # mean/median/std/percentile/CI/effect size (§48)
│   │   ├── reliability_types.py  # metric value objects, verdicts
│   │   └── gateway/
│   │       ├── port.py       # ModelGatewayPort, ChatRequest/ChatResponse
│   │       ├── adapters/     # openai_, anthropic_, gemini_, ollama_, huggingface_
│   │       ├── telemetry.py  # latency/tokens/cost capture (FR-GATEWAY-002)
│   │       ├── retry.py      # transient/permanent classification (§58)
│   │       └── errors.py     # normalized provider errors (§14)
│   ├── jobs/                 # Arq worker functions (executed by workers)
│   │   ├── evaluation.py     # run_evaluation (per-test fan-out)
│   │   ├── test_generation.py
│   │   ├── report.py         # report + export generation
│   │   ├── research.py       # statistical analysis jobs
│   │   ├── alerts.py         # periodic alert evaluation
│   │   ├── aggregation.py    # metric rollups for dashboards
│   │   ├── notifications.py  # in-app/email/webhook dispatch
│   │   └── ingestion.py      # trace/metrics batch writes
│   └── worker.py             # Arq worker entrypoint (settings + job registry)
├── migrations/               # Alembic versions
├── tests/                    # unit (domain), integration (db/redis/gateway), e2e
└── deploy/                   # Dockerfile, compose files, k8s manifests (V2)
```

---

## 2. API Server (FastAPI) Responsibilities

- Serve REST API (`/api/v1/*`), OpenAPI/Swagger auto-generated (§95).
- AuthN/AuthZ middleware + tenancy scoping (see [`SECURITY_ARCHITECTURE.md`](./SECURITY_ARCHITECTURE.md)).
- Synchronous CRUD orchestration for orgs, projects, providers, datasets (metadata), prompts, experiments, environments, admin, audit.
- Job **dispatch**: create `evaluation_runs` / `test_generation` / `report` records and enqueue Arq jobs → returns 202 with job/run id (FR-ASYNC-002).
- Sync read paths for dashboards with Redis-cached aggregates.
- SSE endpoint for live status.
- Health endpoints `/health`, `/ready`, `/live` (§65).
- Request/response logging (no secrets, §94).

## 3. Worker Process (Arq) Responsibilities

Arq is chosen (Redis-native, async, lightweight, zero additional broker cost) over Celery (heavier, more moving parts) and RQ (sync). PRD §67 explicitly allows "Celery/RQ/Arq initially".

- **run_evaluation:** splits dataset version into test batches; executes each test through the Model Gateway against the project's application/model; runs configured evaluators; persists per-test results (partial results preserved on failure, §89); computes metrics, score, regression, quality gate, RCA, recommendations; emits completion events; triggers notifications.
- **test_generation:** generates categorized tests (AC-TESTGEN-001..006), preview state, versioning.
- **report/export:** render report artifacts to object storage (MD/JSON/CSV/PDF).
- **research:** run statistical computations, produce charts + reproducibility metadata (§81).
- **alerts:** periodic evaluation of `alert_rules` against windowed metrics.
- **aggregation:** periodic rollups (P50/P95/P99, error rate, cost) for dashboards.
- **notification dispatch:** in-app + email (via mailer) + webhook.
- **ingestion:** batch persistence of traces/metrics.

Worker capabilities (§57): parallel execution (asyncio + bounded concurrency), retry (Arq retry), timeout, rate limiting (Redis), provider limits (semaphore per provider), partial failure handling (per-test try/except → record fail), job cancellation (Arq task revocation + graceful stop).

## 4. Evaluation Pipeline (domain, framework-free)

```
DatasetVersion ──► Runner ──► ApplicationCall (via ModelGateway)
                     │            │
                     │            ▼
                     │        Response (latency, tokens, cost captured)
                     │            │
                     │            ▼
                     │        Evaluators[] (config per evaluation)
                     │            │
                     │            ▼
                     │        Verdicts + metrics
                     ▼            ▼
               TestResult row   Aggregator ──► metrics ──► ReliabilityScore
                                                  │
                                                  ├─► Regression check
                                                  ├─► Quality gate
                                                  ├─► RCA classification
                                                  └─► Recommendations
```

- `Evaluator` interface: `async analyze(context) -> Verdict` (score, pass/fail/warn, explanation, classification, confidence).
- Evaluators are pure functions over (input, expected, actual, context, meta) — no I/O except optional LLM judge calls → unit-testable at ≥90% coverage (§91).
- LLM-based evaluators (semantic, correctness, hallucination, safety, judge) call the Model Gateway **as the AI Judge** with recorded evaluator model/prompt/version/score/explanation/timestamp (§74).

## 5. Model Gateway (library)

- Port: `chat()` returns normalized `ChatResponse { text, latency, input_tokens, output_tokens, cost, request_id, status }`.
- Adapters: `OpenAIAdapter`, `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter` (OpenAI-compatible, **default local**), `HuggingFaceAdapter`.
- Cross-cutting in gateway: request id, timeout, retry (transient only, max configurable §58), provider rate limiting, cost accounting (versioned pricing config §31), telemetry to OTel, redaction hooks (privacy toggles §60), audit.
- Errors normalized per AC-MODEL-002..004; keys injected server-side only, never logged (AC-MODEL-007).

## 6. Cost & Pricing

- `pricing_configs` (versioned per provider/model) seeded with bundled defaults; org-overridable (AMB-PRICING-001 assumption). Cost = input_tokens × p_in + output_tokens × p_out (BR-COST-002). Aggregates: /request, /1K, /evaluation, /dataset, monthly (§31).

## 7. Scoring Engine (AI Reliability Score)

- Configurable weights; renormalize over available metrics; missing metrics **flagged, not zeroed** (AC-SCORE-003); config snapshot stored with experiment (AC-SCORE-004); output clamped [0,100] (AC-SCORE-001); transparent breakdown returned (FR-SCORE-006).

## 8. Async Job & Retry Semantics

| Concern | Design |
|---------|--------|
| Queue | Redis + Arq (durable enough for MVP; jobs survive API restart — §88) |
| Partial results | Each `test_results` row persisted immediately → no loss on crash (§89) |
| Retry | Transient (timeout, 5xx, rate limit) retried with backoff up to configurable max; permanent (4xx, validation) fail immediately (§58) |
| Timeout | Per-test timeout (from provider config §12); job-level timeout |
| Cancellation | Revoke pending task; in-flight test finishes or aborts gracefully; completed results kept |
| Concurrency | Per-org worker budget + per-provider semaphore + Redis rate limits (§62) |
| Idempotency | Client-supplied `Idempotency-Key` on POST /run, /generate (AMB-API-004 resolution) |

## 9. Event Emission

Services publish domain events through an **outbox pattern** (transactional write to `outbox_events` + relay to Redis pub/sub) so side effects (notifications, alerts, aggregation) are never lost and stay consistent with the DB. Full catalogue in [`EVENT_ARCHITECTURE.md`](./EVENT_ARCHITECTURE.md).

## 10. Background/Periodic Jobs

| Schedule | Job |
|----------|-----|
| Continuous | evaluation, test generation, report, research, ingestion |
| Every minute | alert evaluation |
| Every 5 min | dashboard aggregation rollups |
| Hourly/daily | retention purge (per policy, AMB-RETENTION-001 assumption), cost rollups |

## 11. Testing Strategy (PRD §90–§91)

- Unit: domain evaluators, scoring, regression, gate, dataset parsing, auth, services (pytest, ≥90% for critical/engine).
- Integration: DB (testcontainers/local Postgres), Redis, gateway adapters (Ollama in CI), evaluation pipeline.
- E2E: the §109 journey (Playwright + API).
- AI evaluation tests: golden datasets for evaluators; agreement fixtures for judge.
- Coverage gating in CI (backend ≥80%, critical/engine ≥90%).

## 12. Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| FastAPI | Async, Pydantic validation, auto OpenAPI, Python ML ecosystem (§67) | Django, Flask, Node | FastAPI is younger; fine for MVP | Free | Async I/O scales well | Pydantic input validation, typed |
| SQLAlchemy async | Async DB under FastAPI | Tortoise, raw asyncpg | ORM overhead | Free | Connection pooling | Parameterized queries (SQLi-safe) |
| Arq workers | Redis-native async queue, zero broker cost, matches §67 | Celery, RQ | Smaller ecosystem | Free | Horizontal worker scaling | Worker auth via env config |
| Modular monolith | PRD §108 phases ship working slices; avoids premature microservices | Microservices, serverless | Extraction later requires discipline | Free | Horizontal replicas | Single security boundary easier to audit |
| Framework-free domain | ≥90% coverage on core logic (§91), evaluator testability | Framework-bound services | More interfaces | Free | Pure logic scales trivially | Cleaner invariants (RBAC/tenancy at edges) |
| Outbox + Redis pub/sub | Reliable side effects, decoupling | Direct fan-out, Kafka | Redis pub/sub not durable | Free | Horizontal consumers | Idempotent consumers |
