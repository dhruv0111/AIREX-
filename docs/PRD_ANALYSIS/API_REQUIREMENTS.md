# API Requirements — AIREX

This document enumerates every API the PRD V1.0 requires and documents the level of contract definition provided. The PRD lists endpoint paths (§51) and health endpoints (§65) but does **not** define request/response schemas, authentication schemes, authorization rules, error codes, rate limits, or idempotency semantics for most endpoints. Per the master instructions, such contracts are marked **API CONTRACT NOT DEFINED** and are not invented here.

---

## 1. Core REST Endpoints (from §51)

| # | Method | Endpoint | Auth | Authorization | Request | Response | Errors | Rate limit | Idempotency | Side effects |
|---|--------|----------|------|---------------|---------|----------|--------|------------|-------------|--------------|
| 1 | POST | `/api/v1/projects` | Required (JWT/session) — scheme NS | NS (see AMB-PERM-001) | API CONTRACT NOT DEFINED | API CONTRACT NOT DEFINED | Standard error format (§63); codes NS | NS | NS | Creates project (FR-PROJECT-001) |
| 2 | GET | `/api/v1/projects` | Required | NS | — | API CONTRACT NOT DEFINED | §63 | NS | Read-only | None |
| 3 | GET | `/api/v1/projects/{id}` | Required | Must verify project belongs to caller's org (AC-AUTH-005; AC-SEC-002) | — | API CONTRACT NOT DEFINED | §63 | NS | Read-only | None |
| 4 | POST | `/api/v1/datasets` | Required | NS | API CONTRACT NOT DEFINED | API CONTRACT NOT DEFINED | Row-level import errors (FR-DATASET-012); duplicate ID (FR-DATASET-013) | NS | NS | Creates dataset + initial version (FR-DATASET-008) |
| 5 | GET | `/api/v1/datasets` | Required | NS | — | API CONTRACT NOT DEFINED | §63 | NS | Read-only | None |
| 6 | POST | `/api/v1/datasets/{id}/versions` | Required | NS | API CONTRACT NOT DEFINED | API CONTRACT NOT DEFINED | §63 | NS | NS | Creates immutable dataset version (BR-DATASET-001) |
| 7 | POST | `/api/v1/evaluations` | Required | NS | API CONTRACT NOT DEFINED | API CONTRACT NOT DEFINED | §63 | NS | NS | Creates evaluation referencing exact versions (§78) |
| 8 | GET | `/api/v1/evaluations/{id}` | Required | NS | — | API CONTRACT NOT DEFINED | §63 | NS | Read-only | None |
| 9 | POST | `/api/v1/evaluations/{id}/run` | Required | NS | API CONTRACT NOT DEFINED | Job reference / status (FR-ASYNC-002) | §63 | Evaluation-job rate limit (SEC-RATE-002) | NS | Enqueues async job (FR-ASYNC-001) |
| 10 | POST | `/api/v1/experiments` | Required | NS | API CONTRACT NOT DEFINED | API CONTRACT NOT DEFINED | §63 | NS | NS | Creates experiment (FR-EXPERIMENT-001) |
| 11 | GET | `/api/v1/experiments` | Required | NS | — | API CONTRACT NOT DEFINED | §63 | NS | Read-only | None |
| 12 | POST | `/api/v1/models` | Required | NS | API CONTRACT NOT DEFINED | API CONTRACT NOT DEFINED | §63 | NS | NS | Creates model config; stores encrypted key (SEC-API-001) |
| 13 | GET | `/api/v1/models` | Required | NS | — | API CONTRACT NOT DEFINED | §63 | NS | Read-only | None |
| 14 | POST | `/api/v1/tests/generate` | Required | NS | API CONTRACT NOT DEFINED | Generated tests with categories (FR-TESTGEN-012) | §63; rate limit on test generation (SEC-RATE-002) | NS | NS | Generates versioned test set (AC-TESTGEN-006) |
| 15 | GET | `/api/v1/metrics` | Required | NS | API CONTRACT NOT DEFINED | Metrics payload (§41, §50) | §63 | NS | Read-only | None |
| 16 | POST | `/api/v1/regression/run` | Required | NS | Baseline reference (FR-REGRESSION-001) | Regression result (§36) | §63 | NS | NS | Runs regression comparison |
| 17 | GET | `/api/v1/reports/{id}` | Required | NS | — | Report artifact (§80) | §63 | NS | Read-only | None |

> Note: The endpoint list is not exhaustive relative to the modules (e.g., there are no explicit endpoints for auth, organizations, prompts, alerts, traces, audit logs, research, export, or health of individual resources). The PRD does not claim completeness; missing endpoints are flagged in the [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md) (AMB-API-001).

---

## 2. Health Endpoints (from §65)

| # | Method | Endpoint | Auth | Purpose |
|---|--------|----------|------|---------|
| 18 | GET | `/health` | Public | Liveness/health summary |
| 19 | GET | `/ready` | Public | Readiness — verifies required dependencies (FR/§65) |
| 20 | GET | `/live` | Public | Liveness probe |

- **Contract:** Response body not defined (API CONTRACT NOT DEFINED).
- **Behavior:** Must verify required dependencies (§65) — e.g., PostgreSQL, Redis.

---

## 3. Cross-Cutting API Requirements (from §51, §63, §95)

| Requirement | Status in PRD |
|-------------|---------------|
| Consistent error format for all APIs | Defined: `{ "error": { "code", "message", "request_id" } }` (§63) |
| No internal stack traces to end users | Defined (SEC-ERR-002) |
| Auto-generated API documentation (OpenAPI/Swagger) | Defined (FR-API-004, §95) |
| Every endpoint documents request, response, authentication, errors, example | Defined as a requirement (NFR-DOC-002) |
| Authentication scheme (JWT vs session; bearer vs cookie) | **NOT DEFINED** (§9 mentions "JWT/session") — AMB-API-002 |
| Error code taxonomy | **NOT DEFINED** (single example `EVALUATION_TIMEOUT` given) — AMB-API-003 |
| Rate limits per endpoint | **NOT DEFINED** (categories only: API requests, evaluation jobs, model calls, dataset generation, test generation; per-org configurable — §62) |
| Idempotency keys / retry semantics for POST endpoints | **NOT DEFINED** — AMB-API-004 |
| Pagination / filtering / sorting for list endpoints | **NOT DEFINED** — AMB-API-005 |
| Versioning strategy of the API (v1 already in path) | **NOT DEFINED** |
| Webhook payload format (outbound alert webhooks) | **NOT DEFINED** — AMB-API-006 |
| CLI ↔ API mapping (which CLI commands call which endpoints, auth token handling) | **NOT DEFINED** — AMB-CLI-001 |

---

## 4. CLI Requirements (from §52)

| Command (example) | Purpose | Exit-code contract |
|-------------------|---------|--------------------|
| `airex login` | Authenticate CLI | Meaningful exit codes (§52) — exact codes NS |
| `airex project create` | Create project | Meaningful exit codes |
| `airex dataset upload dataset.jsonl` | Upload dataset | Meaningful exit codes |
| `airex evaluate run --dataset <d> --model <m>` | Run evaluation | Meaningful exit codes |
| `airex regression run --baseline <experiment>` | Run regression | Meaningful exit codes |
| `airex report generate --experiment <e>` | Generate report | Meaningful exit codes |

---

## 5. Summary of Contract Status

| Item | Status |
|------|--------|
| Endpoint path list | **DEFINED** (partial — 17 endpoints + 3 health) |
| Consistent error envelope | **DEFINED** |
| Request/response schemas | **NOT DEFINED** |
| Authentication mechanism | **NOT DEFINED** |
| Authorization rules per endpoint | **NOT DEFINED** |
| Error code taxonomy | **NOT DEFINED** |
| Rate limits | **NOT DEFINED** (categories + per-org configurability defined) |
| Idempotency | **NOT DEFINED** |
| Pagination | **NOT DEFINED** |
| OpenAPI documentation requirement | **DEFINED** |
| CLI command set + exit codes requirement | **DEFINED** |

The API contract is therefore **incomplete**. All undefined items are logged in [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md) (AMB-API-001..006, AMB-CLI-001).
