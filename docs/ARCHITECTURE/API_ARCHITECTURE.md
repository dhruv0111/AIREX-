# API Architecture — AIREX

**Framework:** FastAPI (auto OpenAPI/Swagger per PRD §95). **Style:** REST, `/api/v1`, JSON, consistent error envelope (§63). FastAPI generates the OpenAPI spec that becomes the source of truth for the typed frontend client and CLI.

This document turns the PRD's endpoint list (§51) into a complete, consistent API contract, **resolving the PRD gap** (AMB-API-001..006) with explicit decisions.

---

## 1. API Conventions

| Concern | Decision |
|---------|----------|
| Base path | `/api/v1` |
| Content type | `application/json` (multipart for dataset upload) |
| Auth | User: JWT access token in `Authorization: Bearer` **or** httpOnly cookie (SSR). Programmatic/CI: org API key in `Authorization: Bearer airex_{org}` (server-side only, never returned) |
| Tenant | Derived from JWT/API key claims server-side; client `X-Organization-Id` only switches among the caller's memberships |
| Idempotency | `Idempotency-Key` header on POST /run, /generate, /datasets/…/versions; duplicate keys return the original 202/200 response (AMB-API-004) |
| Pagination | Cursor-based: `?limit=&cursor=` on list endpoints; response `{items, next_cursor}` (AMB-API-005) |
| Filtering | Query params per resource (e.g., `?status=`, `?dataset_version_id=`, `?project_id=`) |
| Errors | Uniform envelope (§63): `{"error": {"code", "message", "request_id"}}`; HTTP status maps to code families |
| Request ID | Every request tagged `X-Request-Id`; echoed in errors and logs (SEC-LOG-001) |
| Rate limiting | Redis sliding window; `X-RateLimit-Limit/Remaining/Reset` headers; per-org configurable (§62) |
| Versioning | Path version `/v1`; additive changes only within v1; breaking changes → v2 |

### Error code families (AMB-API-003 resolution)

| HTTP | Code prefix | Examples |
|------|-------------|----------|
| 400 | `VALIDATION_*` | `VALIDATION_ERROR`, `DATASET_DUPLICATE_ID`, `DATASET_IMPORT_ROW_ERROR` |
| 401 | `AUTH_*` | `AUTH_INVALID_CREDENTIALS`, `AUTH_TOKEN_EXPIRED`, `AUTH_EMAIL_UNVERIFIED` |
| 403 | `AUTHZ_*` | `AUTHZ_FORBIDDEN`, `AUTHZ_CROSS_TENANT`, `AUTHZ_ROLE_REQUIRED` |
| 404 | `NOT_FOUND_*` | `NOT_FOUND_PROJECT`, `NOT_FOUND_DATASET_VERSION` |
| 409 | `CONFLICT_*` | `CONFLICT_ARCHIVED_PROJECT`, `CONFLICT_IMMUTABLE_EXPERIMENT` |
| 429 | `RATE_LIMIT_*` | `RATE_LIMIT_API`, `RATE_LIMIT_EVALUATION` |
| 5xx | `SERVER_*` / provider | `EVALUATION_TIMEOUT`, `MODEL_PROVIDER_ERROR`, `JOB_FAILED` |

---

## 2. Endpoint Catalog

### 2.1 Health (§65) — public
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/ready` | Readiness (checks Postgres, Redis) |
| GET | `/live` | Liveness probe |

### 2.2 Auth (§9)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/auth/register` | FR-AUTH-001; triggers verification email (AC-AUTH-001/002) |
| POST | `/api/v1/auth/verify-email` | AC-AUTH-005 |
| POST | `/api/v1/auth/login` | AC-AUTH-003 |
| POST | `/api/v1/auth/logout` | FR-AUTH-003 |
| POST | `/api/v1/auth/password-reset/request` | FR-AUTH-004 |
| POST | `/api/v1/auth/password-reset/confirm` | FR-AUTH-004 |
| POST | `/api/v1/auth/refresh` | Token refresh |
| GET | `/api/v1/me` | Session profile (user, orgs, active role) |

### 2.3 Organizations (§10)
| Method | Path |
|--------|------|
| POST/GET | `/api/v1/organizations` |
| GET/PATCH | `/api/v1/organizations/{id}` |
| POST | `/api/v1/organizations/{id}/members/invite` (Admin) |
| DELETE | `/api/v1/organizations/{id}/members/{user_id}` (Admin) |
| PATCH | `/api/v1/organizations/{id}/members/{user_id}/role` (Admin) |
| GET | `/api/v1/organizations/{id}/members` |

### 2.4 Projects (§11, §51)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/projects` | Create (FR-PROJECT-001) |
| GET | `/api/v1/projects` | List (paged) |
| GET | `/api/v1/projects/{id}` | Detail |
| PATCH | `/api/v1/projects/{id}` | Edit |
| POST | `/api/v1/projects/{id}/archive` | Archive (FR-PROJECT-003/005) |
| DELETE | `/api/v1/projects/{id}?confirm=true` | Delete with confirmation (FR-PROJECT-004) |

### 2.5 Providers & Models (§12, §51)
| Method | Path | Notes |
|--------|------|-------|
| POST/GET | `/api/v1/models` | CRUD (API-012/013); API key masked on read (FR-PROVIDER-008) |
| GET/PATCH/DELETE | `/api/v1/models/{id}` | |
| POST | `/api/v1/models/{id}/test` | Test inference (AC-MODEL-001..004) |
| POST | `/api/v1/providers` / GET `/api/v1/providers` | Provider config |

### 2.6 Datasets (§15–§16, §51)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/datasets` | Create metadata (API-004) |
| GET | `/api/v1/datasets` | List (API-005) |
| GET | `/api/v1/datasets/{id}` | Detail |
| POST | `/api/v1/datasets/{id}/upload` | multipart import (CSV/JSON/JSONL) → async parse job → row errors (FR-DATASET-012) |
| POST | `/api/v1/datasets/{id}/versions` | Create version (API-006; FR-DATASET-008) |
| GET | `/api/v1/datasets/{id}/versions` | List versions |
| GET | `/api/v1/datasets/{id}/versions/compare?left=&right=` | Version comparison (FR-DATASET-011) |

### 2.7 Tests & Test Generation (§26–§27, §51)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/projects/{id}/tests` | List test cases |
| POST | `/api/v1/tests/generate` | Async generation (API-014; AC-TESTGEN-001..006) → 202 job |
| GET | `/api/v1/tests/generate/{job_id}` | Generation status + preview |
| POST | `/api/v1/tests/{id}/approval` | Approve/reject (AC-TESTGEN-004) |

### 2.8 Evaluations (§17, §51)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/evaluations` | Create (API-007) |
| GET | `/api/v1/evaluations/{id}` | Detail (API-008) |
| GET | `/api/v1/evaluations` | List (paged, filterable) |
| POST | `/api/v1/evaluations/{id}/run` | Async run (API-009) → **202** `{run_id, status: QUEUED}`; idempotent |
| GET | `/api/v1/evaluations/{id}/runs/{run_id}` | Status + metrics (poll) |
| GET | `/api/v1/evaluations/{id}/results` | Test results, failures, classification |
| POST | `/api/v1/evaluations/{id}/runs/{run_id}/cancel` | Cancel job (FR-ASYNC-009) |

### 2.9 Experiments & Comparison (§32–§34, §51)
| Method | Path |
|--------|------|
| POST/GET | `/api/v1/experiments` (API-010/011) |
| GET | `/api/v1/experiments/{id}` |
| POST | `/api/v1/experiments/{id}/run` |
| GET | `/api/v1/experiments/compare?ids=a,b` | Side-by-side (FR-BENCH-004) |
| POST | `/api/v1/experiments/{id}/baseline` | Set baseline (FR-REGRESSION-004) |

### 2.10 Prompts (§33)
| Method | Path |
|--------|------|
| POST/GET | `/api/v1/prompts` |
| GET | `/api/v1/prompts/{id}` / versions |
| POST | `/api/v1/prompts/{id}/versions` |

### 2.11 Regression & Quality Gate (§36–§39)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v1/regression/run` | (API-016) compares candidate vs baseline; returns verdict + deltas |
| GET | `/api/v1/regression/runs/{id}` | |
| PATCH | `/api/v1/projects/{id}/quality-gate` | Configure gate thresholds (§39) |
| GET | `/api/v1/projects/{id}/quality-gate` | |

### 2.12 Observability & Traces (§41–§42)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/metrics` | (API-015) dashboard metrics with time range (§41) |
| GET | `/api/v1/projects/{id}/traces` | List traces (paged) |
| GET | `/api/v1/traces/{id}` | Trace detail + events (§42) |
| POST | `/api/v1/projects/{id}/traces/ingest` | Gateway hook for production app telemetry (server-to-server, API key) |

### 2.13 Alerts (§43–§44)
| Method | Path |
|--------|------|
| POST/GET | `/api/v1/projects/{id}/alert-rules` |
| GET/PATCH/DELETE | `/api/v1/alert-rules/{id}` |
| GET | `/api/v1/projects/{id}/alerts` | Alert feed |

### 2.14 Reports & Export (§79–§80)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/reports/{id}` | (API-017) report metadata/artifact |
| POST | `/api/v1/reports` | Generate report (async job) |
| POST | `/api/v1/export` | Export results (async; CSV/JSON/MD/PDF) |

### 2.15 Research (§47–§49)
| Method | Path |
|--------|------|
| POST/GET | `/api/v1/research/projects` |
| GET/PATCH | `/api/v1/research/projects/{id}` |
| POST/GET | `/api/v1/research/projects/{id}/experiments` |
| GET | `/api/v1/research/experiments/{id}` / `/statistics` |

### 2.16 Admin, Audit, Settings (§61, §68)
| Method | Path |
|--------|------|
| GET | `/api/v1/audit-logs` (Admin) |
| GET/PATCH | `/api/v1/settings` (org settings, privacy toggles §60) |
| POST/GET/DELETE | `/api/v1/organizations/{id}/api-keys` (Admin) |

### 2.17 Streaming
| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/stream` | SSE: evaluation status, alert events, live metrics (cookie auth) |

---

## 3. Async Job Response Pattern

```
POST /api/v1/evaluations/{id}/run   (Idempotency-Key: k-123)
→ 202 Accepted
{
  "run_id": "evrun_01J...",
  "status": "QUEUED",
  "job_id": "job_01K...",
  "poll": "/api/v1/evaluations/{id}/runs/evrun_01J..."
}
```

Poll → `{status: QUEUED|RUNNING|COMPLETED|FAILED, progress: {total, completed, passed, failed}, metrics?, error?}`. Live updates also pushed over SSE.

## 4. Error Response Example (§63)

```
GET /api/v1/projects/999999  (other tenant)
→ 404
{ "error": { "code": "NOT_FOUND_PROJECT",
             "message": "Project not found.",
             "request_id": "req_abc123" } }
```

Cross-tenant IDs return 404 (not 403) to avoid resource enumeration (AC-SEC-002).

## 5. API Security Notes

- OpenAPI/Swagger exposed (documentation per §95) but mutation requires auth.
- All mutating endpoints enforce RBAC + tenancy via middleware (see [`SECURITY_ARCHITECTURE.md`](./SECURITY_ARCHITECTURE.md)).
- Rate limiting applied per org per scope (§62): API, evaluation jobs, model calls, dataset generation, test generation.
- Secrets never in responses except masked placeholders (AC-SEC-003).

## 6. Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| FastAPI auto-OpenAPI | PRD §95; single source of truth for client+CLI | Hand-written docs | Generated spec needs review | Free | — | Contract-first validation |
| Cursor pagination | Consistent, stable under writes | Offset pagination | Slightly more complex client | Free | Scales for large lists | Prevents offset scan DoS |
| Idempotency keys | CI retries (AC-CICD) must not duplicate runs (AMB-API-004) | None | Cache of keys | Free | Redis-backed | Prevents duplicate side effects |
| 404 for cross-tenant | Prevent resource enumeration (AC-SEC-002) | 403 | None | Free | — | Stronger |
| SSE stream | Live dashboards/job progress | WebSocket | One-way only | Free | Redis fan-out | Cookie-auth |
