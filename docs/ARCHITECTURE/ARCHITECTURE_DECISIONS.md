# Architecture Decisions — AIREX

This is the decision register for the AIREX technical architecture. It contains:

1. **Architecture Decision Records (ADR)** — every significant decision with WHY / ALTERNATIVES / TRADEOFFS / COST / SCALABILITY / SECURITY.
2. **Assumption Register** — how each PRD ambiguity (from the [`AMBIGUITY_REGISTER.md`](../PRD_ANALYSIS/AMBIGUITY_REGISTER.md)) is resolved by the architecture.
3. **Requirement → Owner Coverage Matrix** — the basis for the final **ARCHITECTURE READY** verdict.

---

# Part 1 — Architecture Decision Records

## ADR-001: Modular monolith (FastAPI) + separate Arq worker process

- **Decision:** One FastAPI application exposing the API; a separate worker process running Arq jobs; both share a common `airex` package (domain + services + repositories).
- **WHY:** PRD §108 mandates phased, always-working vertical slices; microservices would multiply cost/ops before scale is justified. A shared domain library keeps the evaluation engine (the core) testable at ≥90% coverage (§91) while API and workers stay separate processes.
- **ALTERNATIVES:** (a) Microservices per module — premature; high ops cost. (b) Single process doing sync evaluation — violates FR-ASYNC-002 (API not blocked). (c) Celery — heavier, extra broker semantics.
- **TRADEOFFS:** Module extraction later requires discipline; one deployable with two entrypoints (api vs worker). Simpler than microservices; still satisfies async.
- **COST:** $0 (open source).
- **SCALABILITY:** API replicas scale horizontally (stateless); workers scale by queue depth; domain scales trivially.
- **SECURITY:** Single trust boundary; RBAC/tenancy enforced at edges; worker has no public surface.

## ADR-002: Arq (Redis) as the job queue

- **Decision:** Arq over Redis for background jobs.
- **WHY:** Redis already required (§55); Arq is async-native and zero extra infrastructure; PRD §67 explicitly permits "Celery/RQ/Arq initially".
- **ALTERNATIVES:** Celery (heavier, needs beat/flower), RQ (sync workers), SQS (paid, needs adapter), Kafka (overkill for MVP).
- **TRADEOFFS:** Arq's ecosystem is smaller; Redis isn't a durable queue by itself → we add the transactional outbox + idempotent re-enqueue for §88–§89 reliability.
- **COST:** $0.
- **SCALABILITY:** Horizontal workers; per-provider semaphores; per-org budgets (§62).
- **SECURITY:** No public surface; worker auth via shared settings.

## ADR-003: PostgreSQL + pgvector as the single primary store

- **Decision:** PostgreSQL 16 with pgvector; RLS enabled on tenant tables.
- **WHY:** PRD §53–§54 specify PostgreSQL and pgvector initially; single store reduces ops; RLS gives defense-in-depth for AC-SEC-001/002.
- **ALTERNATIVES:** Separate vector DB (later, behind `VectorStorePort`), MySQL/NoSQL.
- **TRADEOFFS:** pgvector matures with Postgres; very large vector corpora may need external store later (§54).
- **COST:** $0 (free/local; managed RDS optional in prod).
- **SCALABILITY:** Partitioning for traces/metrics; HNSW vector index; read replicas later.
- **SECURITY:** RLS + tenant-scoped repositories + parameterized queries.

## ADR-004: JWT access + rotating refresh; org API keys for programmatic/CI access

- **Decision:** JWT (short access, rotating refresh) for users; hashed org API keys for CLI/CI.
- **WHY:** Stateless auth scales; API keys satisfy CI/CD (AC-CICD-001..005) and programmatic use without sessions; keys are hash-stored (AC-SEC-003).
- **ALTERNATIVES:** Opaque server sessions (stateful, more DB load), OAuth2 machine creds (heavier for MVP), no API keys.
- **TRADEOFFS:** Token revocation is explicit (refresh rotation + key revocation); SSO deferred to V3.
- **COST:** $0 (PyJWT, argon2-cffi).
- **SCALABILITY:** Stateless verification; Redis for refresh allowlist.
- **SECURITY:** httpOnly cookies (web), Bearer for API, keys hash-only, immediate revocation on user removal (AC-SEC-004).

## ADR-005: Transactional outbox + Redis pub/sub + SSE

- **Decision:** Side effects (notifications, alerts, aggregation, CI callbacks) are driven by an outbox table → Redis pub/sub → idempotent consumers; web app receives live updates over SSE.
- **WHY:** Reliable side effects with DB consistency (§89), decoupled modules, zero-cost, live dashboards (J8/J15/J16).
- **ALTERNATIVES:** Kafka (paid/ops), direct fan-out (loss risk), WebSocket (unnecessary for one-way updates).
- **TRADEOFFS:** Pub/sub is not durable → outbox compensates; SSE is one-way.
- **COST:** $0.
- **SCALABILITY:** Horizontal consumers; fan-out per org.
- **SECURITY:** Cookie-authed SSE; idempotent consumers prevent duplicate effects.

## ADR-006: Ports-and-adapters for all paid integrations

- **Decision:** Model gateway, storage, mail, vector store, webhook, and (future) identity all behind ports; local/free adapters are the default.
- **WHY:** "Prioritize zero-cost/local implementations; design paid-provider adapters but do not require paid services" (user directive + PRD §67). Ollama + MinIO + MailHog + local Postgres/Redis give full local parity.
- **ALTERNATIVES:** Hard-coding SDKs (blocks local dev), abstracting only models (insufficient).
- **TRADEOFFS:** More interfaces; per-adapter testing needed.
- **COST:** $0 local; paid adapters optional.
- **SCALABILITY:** Swap adapters as scale requires.
- **SECURITY:** Secrets isolated per adapter; never in logs.

## ADR-007: Reliability Score = normalized weighted sum over available metrics, missing metrics flagged

- **Decision:** Score = Σ(wᵢ·mᵢ)/Σ(wᵢ over present metrics) × 100, clamped [0,100]; missing metrics reported, never zero-filled; config snapshot stored with each experiment.
- **WHY:** Satisfies AC-SCORE-001..004 exactly (0–100, recalc on weight change, missing ≠ zero, config persisted) and PRD §83 (transparent).
- **ALTERNATIVES:** Zero-fill missing (violates AC-SCORE-003), require all metrics (reduces usability).
- **TRADEOFFS:** Score comparability depends on which metrics present → we surface coverage.
- **COST:** $0.
- **SCALABILITY:** Pure function; trivial.
- **SECURITY:** Weights/config tenant-scoped and versioned.

## ADR-008: Tenant-scoped repository + PostgreSQL RLS (defense in depth)

- **Decision:** All data access goes through tenant-scoped repositories that inject `organization_id`; RLS enabled as a second barrier; cross-tenant IDs return 404.
- **WHY:** AC-SEC-001/002, AC-AUTH-005; prevents IDOR even if a controller omits a filter.
- **ALTERNATIVES:** Middleware-only scoping, per-query manual filters.
- **TRADEOFFS:** RLS overhead (small) and schema discipline.
- **COST:** $0.
- **SCALABILITY:** Indexed tenant columns.
- **SECURITY:** Strongest reasonable multi-tenant isolation.

## ADR-009: 404 (not 403) for cross-tenant resource access

- **Decision:** Unauthorized cross-tenant resource access returns 404.
- **WHY:** Prevents resource enumeration (AC-SEC-002); consistent with "Project IDs cannot be used to bypass authorization."
- **ALTERNATIVES:** 403 (leaks existence).
- **TRADEOFFS:** Slightly less informative errors.
- **COST:** $0.
- **SCALABILITY:** —.
- **SECURITY:** Stronger.

## ADR-010: Framework-free domain core (evaluators, scoring, regression, gate, stats)

- **Decision:** Evaluation and scoring logic live in `airex/domain/` with no framework imports.
- **WHY:** §91 requires ≥90% coverage of the evaluation engine and critical logic; pure logic is trivially unit-testable and reusable by workers/API.
- **ALTERNATIVES:** Framework-bound services (harder to test, slower CI).
- **TRADEOFFS:** Extra interfaces at the edges.
- **COST:** $0.
- **SCALABILITY:** Pure logic parallelizes.
- **SECURITY:** Cleaner enforcement of invariants (RBAC/tenancy at edges).

## ADR-011: Cursor pagination + idempotency keys + SSE

- **Decision:** List endpoints use cursor pagination; POST /run and /generate accept `Idempotency-Key`; live updates over SSE.
- **WHY:** Resolves AMB-API-004/005; stable under writes; CI retries must not duplicate runs (AC-CICD).
- **ALTERNATIVES:** Offset pagination, no idempotency.
- **TRADEOFFS:** Slightly more client complexity.
- **COST:** $0.
- **SCALABILITY:** Cursor avoids deep-offset scans.
- **SECURITY:** Prevents duplicate side effects.

## ADR-012: Implicit-acknowledgment of PRD ambiguities via documented assumptions (not silent fixes)

- **Decision:** Where the PRD is silent or ambiguous, the architecture records an explicit assumption (Part 2) rather than silently choosing. Owners are assigned for every requirement regardless, so implementation can proceed while the product owner reviews the assumptions.
- **WHY:** The analysis declared "PRD REQUIRES CLARIFICATION." The user directive now asks for a complete architecture with every requirement owning an architectural component; assumptions make that possible without hiding the gaps.
- **ALTERNATIVES:** Block on clarification (no architecture deliverable), or silently guess (violates the PRD-analysis principles).
- **TRADEOFFS:** Assumptions may later be overturned by the product owner — they are each linked to an ambiguity ID for easy review.
- **COST:** $0.
- **SCALABILITY:** —.
- **SECURITY:** Assumptions default to least-privilege / safe defaults.

---

# Part 2 — Assumption Register (resolves PRD ambiguities)

Every assumption below is **flagged for product-owner confirmation** and traces to the Ambiguity Register.

| Ambiguity | Architectural assumption (ADR owner) |
|-----------|--------------------------------------|
| AMB-VERSION-SCOPE-001 (MVP vs V2) | Architecture covers the **full product** (all PRD sections). Delivery ordering follows §108; research workspace, human review, RCA, recommendations are designed and owned, implemented in later phases. MVP gate list (§96) is treated as the v1 delivery scope; §101 items 33/35 and §102 steps 17–20 are scheduled in the research/review phase. Owner: product owner to confirm sequencing. |
| AMB-API-001..006 | Full API contract resolved in [`API_ARCHITECTURE.md`](./API_ARCHITECTURE.md): JWT bearer + org API keys, error-code families, cursor pagination, idempotency keys, SSE, HMAC webhooks. |
| AMB-BILLING-001 | Platform billing/subscription **out of MVP scope** (PRD §96 omits it). Only AI inference cost analytics is built (§31). A future `BillingPort` is intentionally not designed. |
| AMB-DATA-SCHEMA-001 | Full schema designed in [`DATABASE_ARCHITECTURE.md`](./DATABASE_ARCHITECTURE.md) incl. implied entities (pricing configs, human reviews, score configs, notifications, outbox, vector chunks). |
| AMB-THRESHOLD-001 | Thresholds are **per-project/org configuration** (Admin-configured policies, §7). Absolute (quality gate §39) and relative (regression deltas §37) rule types are distinct; bundled example defaults are seed data, not hard-coded. |
| AMB-PERM-001 | Granular RBAC resolved with **least-privilege defaults** in [`PERMISSION_MATRIX.md`](../PRD_ANALYSIS/PERMISSION_MATRIX.md) + [`SECURITY_ARCHITECTURE.md`](./SECURITY_ARCHITECTURE.md) (ADR-SEC-002). Org-scoped roles; project-level permissions via membership. |
| AMB-RETENTION-001 / AMB-PRIVACY-001 | Retention tiers + default toggles (raw storage OFF, masking ON) resolved in [`DATABASE_ARCHITECTURE.md`](./DATABASE_ARCHITECTURE.md) §6 and [`SECURITY_ARCHITECTURE.md`](./SECURITY_ARCHITECTURE.md) §6. |
| AMB-PRICING-001 | Versioned pricing configs seeded with bundled defaults, org-overridable; cost estimates per §31. |
| AMB-CICD-002 | CI auth = org API key; trigger + poll/callback + exit codes per AC-CICD-001..005; sample GitHub Actions workflow ships. |
| AMB-JUDGE-001 | AI Judge configurable per org via the model gateway (default local Ollama); all §74 fields recorded. |
| AMB-EMAIL-001 / AMB-STORAGE-001 | SMTP (MailHog local / SES prod) and S3-compatible storage (MinIO local / S3 prod) adapters. |
| AMB-ONBOARD-001 | Auto-create organization at signup with creator as Admin; Admin may create more (§7). |
| AMB-EVAL-001 | MVP evaluator set = §96 list; underspecified evaluators (data leakage, response format, consistency) defined with concrete semantics in the domain module; additional refinements deferred. |
| AMB-ARCHIVE-001 | Archived projects are **fully read-only** (no new evaluations in any environment) — safest interpretation; flagged for confirmation. |
| AMB-CONF-001 | Confidence = normalized AI-judge score with recorded methodology; low-confidence cutoff configurable. |
| AMB-ASYNC-001 | Cancellation = graceful (preserve completed); partial failures = retry-transient then record FAIL; per-test status exposed. |
| AMB-RATE-001 / AMB-SCALE-001 | Default rate limits + MVP concurrency (10 concurrent evaluations/org, 20 max workers, per-provider semaphore 8) set in [`INFRASTRUCTURE.md`](./INFRASTRUCTURE.md) §9 and [`SECURITY_ARCHITECTURE.md`](./SECURITY_ARCHITECTURE.md) §7. |
| AMB-NOTIF-001 | Notifications scoped to project/org with user preferences (in-app always; email opt-in; webhook per-org). |
| AMB-HUMAN-001 | Single reviewer per sampled item initially; store all decisions; double-review configurable. |
| AMB-TESTGEN-001 | Max quantity + per-org monthly generation budget; content moderation on generated tests. |
| AMB-PROVIDER-001 / AMB-VECTOR-001 | OSS/local via OpenAI-compatible HTTP; embedding model versioned per project (pgvector default). |
| AMB-INDEX-001 / AMB-UNIQUE-001 | Indexing plan in [`DATABASE_ARCHITECTURE.md`](./DATABASE_ARCHITECTURE.md) §7; ULID/BIGINT IDs with tenant-scoped unique constraints. |
| AMB-COMPLIANCE-001 | V1 = secure-by-design, no formal certification; governance/compliance in V3 (§98). |
| AMB-AC-001 | Modules lacking ACs (observability, alerting, RCA, recommendations, reporting, research, accessibility, availability) receive testable ACs at implementation time (flagged in [`ACCEPTANCE_CRITERIA.md`](../PRD_ANALYSIS/ACCEPTANCE_CRITERIA.md) §6). |
| AMB-CLI-001 | CLI stores a scoped org API key locally; commands map 1:1 to API endpoints; standard exit codes. |

---

# Part 3 — Requirement → Owner Coverage Matrix

Every requirement group from the [`REQUIREMENT_INVENTORY.md`](../PRD_ANALYSIS/REQUIREMENT_INVENTORY.md) is owned by one or more architectural components. **Owner** = the component/design document that will implement and test it. This is the basis for the **ARCHITECTURE READY** verdict.

| Requirement group | IDs | Architectural owner(s) | Design ref |
|-------------------|-----|------------------------|------------|
| Authentication & Authorization | FR-AUTH-001..014 | API Server (auth service) + Mailer + Redis + Security middleware | API, SECURITY |
| Organization Management | FR-ORG-001..007 | API Server (org service) + Postgres + Audit | SYSTEM, DATABASE |
| Project Management | FR-PROJECT-001..006 | API Server (project service) | API, DATABASE |
| AI Provider Management | FR-PROVIDER-001..008 | Provider service + Model Gateway + Secrets | BACKEND, SECURITY |
| Model Gateway | FR-GATEWAY-001..009 | Model Gateway library (adapters, telemetry, retry, errors) | BACKEND, INTEGRATION |
| Dataset Management | FR-DATASET-001..013 | Dataset service + Worker (parse) + Object Storage + Postgres | BACKEND, DATABASE, API |
| Evaluation Engine | FR-EVAL-001..027 | Workers + domain evaluators + scoring + Model Gateway | BACKEND, DATABASE |
| AI Test Generator | FR-TESTGEN-001..016 | Worker (test_generation) + Gateway + Postgres | BACKEND, EVENT |
| Prompt Injection Testing | FR-PROMPTINJ-001..004 | Safety evaluator + authz guard | BACKEND, SECURITY |
| Safety Evaluation | FR-SAFETY-001..008 | Safety evaluators (domain) | BACKEND |
| Performance Evaluation | FR-PERF-EVAL-001..009 | Gateway telemetry + aggregation worker + metrics tables | BACKEND, DATABASE |
| Cost Evaluation | FR-COST-001..007 | Cost engine + versioned pricing configs | BACKEND, DATABASE |
| Model Benchmarking | FR-BENCH-001..004 | Experiment/comparison service + workers | BACKEND, API |
| Prompt Experimentation | FR-PROMPT-001..003 | Prompt service + prompt_versions | BACKEND, DATABASE |
| Experiment Management | FR-EXPERIMENT-001..002 | Experiment service + immutable tables | BACKEND, DATABASE |
| Reproducibility | FR-REPRO-001..002 | Versioning data layer + reproducibility metadata | DATABASE, BACKEND |
| Regression Testing | FR-REGRESSION-001..004 | Regression worker + baselines + thresholds | BACKEND, API |
| CI/CD Integration | FR-CICD-001..006 | CI trigger API + CLI + Quality gate | API, INTEGRATION |
| Production Observability | FR-OBS-001..007 | Ingest path + trace tables + aggregation + frontend | BACKEND, DATABASE, EVENT |
| Alerting | FR-ALERT-001..011 | Alert evaluator worker + notifier + alert tables | EVENT, BACKEND |
| Root Cause Analysis | FR-RCA-001..002 | RCA worker + failure classification | BACKEND |
| Recommendation Engine | FR-RECO-001..003 | Recommendation worker | BACKEND |
| Research Workspace | FR-RESEARCH-001..015 | Research service + stats worker + report renderer | BACKEND, API, DATABASE |
| Dashboard | FR-DASH-001..006 | Frontend + metrics API + aggregation | FRONTEND, API |
| API | FR-API-001..004 | API Server + OpenAPI | API |
| CLI | FR-CLI-001..003 | CLI package (`airex`) | API, INTEGRATION |
| Reporting & Export | FR-REPORT-001..008 | Report worker + object storage + renderer | BACKEND, DATABASE |
| Human Review & Calibration | FR-HUMAN-001..006 | Human review service + frontend + calibration tables | BACKEND, FRONTEND, DATABASE |
| AI Judge & Confidence | FR-JUDGE-001..004 | Gateway (judge) + judge_judgments table | BACKEND, DATABASE |
| Environment Management | FR-ENV-001..003 | Environment service + tenant-scoped credentials | BACKEND, SECURITY |
| Versioning | FR-VERSION-001..002 | Versioned data layer (FKs to version rows) | DATABASE |
| AI Reliability Score | FR-SCORE-001..006 | Scoring engine (domain) | BACKEND |
| Notifications | FR-NOTIFY-001..006 | Notifier worker + events + mailer/webhook | EVENT, INTEGRATION |
| Async Evaluation & Workers | FR-ASYNC-001..013 | Arq workers + Redis + outbox | BACKEND, EVENT, INFRASTRUCTURE |
| Non-functional (NFR) | NFR-PERF/RELI/OBS/TEST/DOC-* | Infrastructure + observability + CI | INFRASTRUCTURE, API |
| UX / Accessibility | UX-001..007 | Frontend | FRONTEND |
| Security (SEC) | SEC-* | Security middleware, secrets, redaction, audit, rate limit | SECURITY |
| Performance (PERF) | PERF-001..005 | API + gateway + aggregation + infra | INFRASTRUCTURE, BACKEND |
| Data (DATA) | DATA-001..006, DATA-PRIV/VOL* | Database + object storage + Redis | DATABASE |
| API (API) | API-001..020 | API Server + OpenAPI | API |
| Infrastructure (INFRA) | INFRA-001..008 | Compose/ECS/EKS + health + observability | INFRASTRUCTURE |
| Integration (INT) | INT-001..011 | Adapters (gateway, storage, mail, vector, CI, SSO-V3) | INTEGRATION |
| Compliance (COMP) | COMP-001..005 | Security + retention + audit | SECURITY, DATABASE |
| Analytics (ANA) | ANA-001..007 | Metrics API + aggregation + stats worker + dashboards | BACKEND, FRONTEND |
| Billing (BILL) | BILL-001..005 | Cost engine + versioned pricing (analytics only) | BACKEND |
| Administration (ADM) | ADM-001..010 | Admin service + audit + frontend | API, BACKEND, FRONTEND |
| Master AC (§101) & E2E (§102) & Release Gate (§109) | — | E2E test suite + CI gates (owner: CI/QA) | INFRASTRUCTURE, ACCEPTANCE |

**Coverage result:** All 13 requirement categories and every requirement group from the inventory have an assigned architectural owner. No requirement is left without a component, schema, or design reference.

---

# Final Verdict

- Every PRD requirement group has an **architectural owner** (Part 3).
- Every PRD ambiguity that would block design has an **explicit, documented assumption** for product-owner review (Part 2), resolving the gaps flagged in the analysis phase without silent fixes.
- Architecture is **zero-cost / local-first** (Ollama, MinIO, MailHog, local Postgres/Redis); paid providers are optional adapters only.
- No code has been written.

> ## ARCHITECTURE READY

The architecture is ready for implementation planning (per PRD §108 phases). Remaining inputs from the product owner are **confirmations of the assumptions** in Part 2 (each mapped to an ambiguity ID) — these do not block architecture, but should be confirmed before each affected phase begins.
