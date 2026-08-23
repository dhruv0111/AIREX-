# API Contracts — AIREX

Complete REST contracts derived from the PRD (§51, §63, §95), the architecture ([`API_ARCHITECTURE.md`](../ARCHITECTURE/API_ARCHITECTURE.md)), and the business rules. This is the authoritative contract; the implementation generates OpenAPI from it.

**Conventions:**
- Base path `/api/v1`; JSON; UTC timestamps (ISO 8601); UUIDs as strings.
- Auth headers: `Authorization: Bearer <jwt|org-api-key>` or httpOnly session cookie (web SSR).
- Tenant: active org derived from token claims; optional `X-Organization-Id` to switch among caller's memberships (never used to elevate).
- Common headers: `X-Request-Id` (echoed), `Idempotency-Key` (POST /run, /generate, /versions), rate-limit headers.
- Errors: uniform envelope (see [`ERROR_CONTRACTS.md`](./ERROR_CONTRACTS.md)).
- Roles: `A`=Admin, `PO`=Project Owner, `E`=Engineer, `V`=Viewer (least-privilege defaults per [`PERMISSION_MATRIX.md`](../PRD_ANALYSIS/PERMISSION_MATRIX.md)).
- Rate-limit scopes: `api`, `eval`, `model`, `dataset_gen`, `test_gen` (§62), per-org configurable.
- `◇` denotes a tenant-scoped resource.

---

## 1. Health (public)

### GET /health, GET /live, GET /ready
| Field | Value |
|-------|-------|
| Auth | None |
| Rate limit | None |
| Response (200) | `{"status":"ok","version":"1.0.0","checks":{"postgres":"ok","redis":"ok"},"timestamp":"..."}` (degraded → 503 with failing checks) |

---

## 2. Authentication (public except /me, /logout)

### POST /api/v1/auth/register
| Field | Value |
|-------|-------|
| Auth | None |
| Request | `{"email":"string","password":"string(min 8)","full_name":"string"}` |
| Response | 201 `{"user_id":"123","email":"...","status":"pending","email_verified":false}` (triggers verification email, AC-AUTH-001/002/005) |
| Errors | 400 `VALIDATION_ERROR`, 409 `AUTH_EMAIL_EXISTS` (AC-AUTH-002), 429 `RATE_LIMIT_AUTH` |
| Rate limit | 10/hour/IP |

### POST /api/v1/auth/login
| Field | Value |
|-------|-------|
| Request | `{"email":"string","password":"string"}` |
| Response | 200 `{"access_token":"jwt","refresh_token":"jwt","token_type":"bearer","expires_in":900}` (+ sets httpOnly cookie when `?cookie=true` for SSR) |
| Errors | 401 `AUTH_INVALID_CREDENTIALS` (AC-AUTH-003), 403 `AUTH_EMAIL_UNVERIFIED`, 429 `RATE_LIMIT_AUTH` (5/min/account) |
| Audit | user.login (§61) |

### POST /api/v1/auth/refresh
| Field | Value |
|-------|-------|
| Request | `{"refresh_token":"jwt"}` (or cookie) |
| Response | 200 `{"access_token":"jwt","refresh_token":"jwt"}` (rotation) |
| Errors | 401 `AUTH_TOKEN_EXPIRED`, `AUTH_TOKEN_REVOKED` |

### POST /api/v1/auth/logout — 204; revokes refresh; audit user.logout.
### POST /api/v1/auth/verify-email
- Request `{"token":"signed"}` → 200; errors 400 `AUTH_INVALID_TOKEN`, 410 `AUTH_TOKEN_EXPIRED`.

### POST /api/v1/auth/password-reset/request
- Request `{"email":"string"}` → 202 always (no enumeration). Audit.
### POST /api/v1/auth/password-reset/confirm
- Request `{"token":"signed","password":"string(min 8)"}` → 200; errors 400/410.

### GET /api/v1/me
| Field | Value |
|-------|-------|
| Auth | JWT |
| Response | 200 `{"user_id":"..","email":"..","organizations":[{"organization_id":"..","role":"admin|project_owner|engineer|viewer"}],"active_organization_id":".."}` |
| Errors | 401 `AUTH_TOKEN_EXPIRED` |

---

## 3. Organizations (roles: A manage, others view their own)

### POST /api/v1/organizations
- Request `{"name":"string","slug":"string","privacy_policy":{...}}` → 201 org; creator becomes Admin (AMB-ONBOARD-001). Errors 409 `CONFLICT_ORGANIZATION_SLUG`.
### GET /api/v1/organizations — 200 list (paged).
### GET /api/v1/organizations/{id} — 200; cross-tenant → 404.
### PATCH /api/v1/organizations/{id} — A only; update settings/privacy toggles (§60).
### POST /api/v1/organizations/{id}/members/invite — A
- Request `{"email":"string","role":"project_owner|engineer|viewer"}` → 202 (invite email). Errors 409 `AUTH_EMAIL_EXISTS`.
### DELETE /api/v1/organizations/{id}/members/{user_id} — A → 204; immediate revocation (AC-SEC-004).
### PATCH /api/v1/organizations/{id}/members/{user_id}/role — A; `{"role":"..."}` → 200.
### GET /api/v1/organizations/{id}/members — A → list.

---

## 4. Projects

| Method | Path | Auth | Roles | Idempotency | Notes |
|--------|------|------|-------|-------------|-------|
| POST | /api/v1/projects | JWT/API-key | A, PO | Key optional | 201; body §11 config |
| GET | /api/v1/projects | JWT | all | — | paged `?limit=&cursor=&archived=` |
| GET | /api/v1/projects/{id} | JWT | all | — | cross-tenant → 404 |
| PATCH | /api/v1/projects/{id} | JWT | A, PO | — | 200 |
| POST | /api/v1/projects/{id}/archive | JWT | A, PO | — | 200; archived blocks new production evals (FR-PROJECT-005) |
| DELETE | /api/v1/projects/{id}?confirm=true | JWT | A, PO | — | 204 only with `confirm=true` (FR-PROJECT-004) |

**Request (POST /projects):**
```json
{
  "name": "Enterprise AI Assistant",
  "description": "RAG chatbot",
  "application_type": "rag_chatbot",
  "environment": "production",
  "endpoint": "https://app.example.com/chat",
  "endpoint_auth": {"type": "bearer", "token_ref": "sec_..."},
  "model_config": {"default_model_id": 42},
  "evaluation_config": {"default_evaluation_config_id": 7}
}
```
**Response (201):** `{"id":"123","name":"...","environment":"production","archived":false,"created_at":"..."}`

---

## 5. Providers & Models

| Method | Path | Auth | Roles | Notes |
|--------|------|------|-------|-------|
| POST | /api/v1/providers | JWT | A, PO | create provider (§12) |
| GET | /api/v1/providers | JWT | all | list |
| POST | /api/v1/models | JWT | A, PO | body: provider_id, name, model_ref, api_key, base_url, temperature, max_tokens, timeout_ms, retry_policy (§12) |
| GET | /api/v1/models | JWT | all | list (api_key masked as `"sk-••••1234"`) (FR-PROVIDER-008) |
| GET | /api/v1/models/{id} | JWT | all | masked |
| PATCH | /api/v1/models/{id} | JWT | A, PO | update config (key masked) |
| DELETE | /api/v1/models/{id} | JWT | A, PO | 204 |
| POST | /api/v1/models/{id}/test | JWT | A, PO, E | test inference; 200 `{"request_id":"..","ok":true,"latency_ms":..}`; errors per AC-MODEL-002..004 |

**Model create response (201):**
```json
{"id":"42","name":"gpt","provider_id":"5","model_ref":"gpt-4o",
 "api_key":"sk-••••1234","temperature":0.2,"max_tokens":1024,
 "timeout_ms":60000,"retry_policy":{"max_retries":3,"backoff":"exponential"},
 "status":"active"}
```

---

## 6. Datasets

| Method | Path | Auth | Roles | Notes |
|--------|------|------|-------|-------|
| POST | /api/v1/datasets | JWT | A, PO, E | create metadata; `{"project_id","name","dataset_id","source_format"}` |
| GET | /api/v1/datasets | JWT | all | paged |
| GET | /api/v1/datasets/{id} | JWT | all | |
| POST | /api/v1/datasets/{id}/upload | JWT | A, PO, E | multipart `file` (csv/json/jsonl) → 202 `{"upload_id","job_id"}`; async parse; per-row errors delivered via status + `GET .../upload/{upload_id}` |
| POST | /api/v1/datasets/{id}/versions | JWT | A, PO, E | Idempotency-Key; creates version (FR-DATASET-008); 201 version |
| GET | /api/v1/datasets/{id}/versions | JWT | all | |
| GET | /api/v1/datasets/{id}/versions/compare?left=&right= | JWT | all | 200 diff (FR-DATASET-011) |
| DELETE | /api/v1/datasets/{id} | JWT | A, PO | 204; audit "dataset deleted" (§61) |

**Upload status (GET /api/v1/datasets/{id}/upload/{upload_id}):**
```json
{"upload_id":"..","status":"processing|completed|failed",
 "total_rows":1000,"succeeded":995,"failed":5,
 "row_errors":[{"row":12,"error":"missing required field 'input'","code":"DATASET_IMPORT_ROW_ERROR"}]}
```

---

## 7. Test Cases & Test Generation

### POST /api/v1/tests/generate
| Field | Value |
|-------|-------|
| Auth | JWT/API-key; roles A, PO, E |
| Request | `{"project_id":"..","count":100,"inputs":{"application_description":"..","dataset_version_id":"..","documentation":"..","existing_tests":[]}}` (AC-TESTGEN-001/002) |
| Response | 202 `{"generation_id":"..","status":"queued","job_id":"..","poll":"/api/v1/tests/generate/{generation_id}"}` |
| Idempotency | `Idempotency-Key` required |
| Rate limit | `test_gen` scope (§62); max `count` per org budget (AMB-TESTGEN-001) |
| Errors | 429 `RATE_LIMIT_TEST_GENERATION`, 400 `VALIDATION_ERROR`, 422 generation failure |

### GET /api/v1/tests/generate/{generation_id}
- 200 `{"status":"queued|running|preview_ready|completed|failed","tests":[{"id","category","input","expected_output","approval_status":"pending"}]}`
### POST /api/v1/tests/{id}/approval
- `{"approval_status":"approved|rejected"}` → 200 (AC-TESTGEN-004/005).
### GET /api/v1/projects/{id}/tests — paged list.

---

## 8. Evaluations

### POST /api/v1/evaluations
| Field | Value |
|-------|-------|
| Auth | JWT/API-key; A, PO, E |
| Request | `{"project_id":"..","dataset_version_id":"..","model_id":"..","model_version":"..","prompt_version_id":"..","evaluation_config_id":"..","environment":"development","triggered_by":"user"}` |
| Response | 201 `{"id":"..","status":"draft"}` (versions pinned, §78) |
| Errors | 400 `VALIDATION_ERROR`, 409 `CONFLICT_ARCHIVED_PROJECT`, 404 `NOT_FOUND_DATASET_VERSION` |

### POST /api/v1/evaluations/{id}/run
| Field | Value |
|-------|-------|
| Auth | JWT/API-key; A, PO, E |
| Request | `{}` (config already on evaluation) |
| Response | **202** `{"run_id":"evrun_..","status":"QUEUED","job_id":"job_..","poll":"/api/v1/evaluations/{id}/runs/{run_id}"}` (FR-ASYNC-001/002) |
| Idempotency | `Idempotency-Key` — duplicate key returns same 202 (AMB-API-004) |
| Rate limit | `eval` scope |
| Errors | 409 `CONFLICT_RUN_IN_PROGRESS`, 429 `RATE_LIMIT_EVALUATION` |

### GET /api/v1/evaluations/{id}/runs/{run_id}
```json
{"run_id":"..","status":"QUEUED|RUNNING|COMPLETED|FAILED|CANCELLED",
 "progress":{"total":100,"completed":80,"passed":76,"failed":3,"warning":1},
 "metrics":null,
 "score":null,
 "error":null}
```
- On COMPLETED, adds `metrics`, `score`, `regression_status`, `quality_gate_status`.
### GET /api/v1/evaluations/{id}/results — per-test results (paged; filters `?status=fail`).
### POST /api/v1/evaluations/{id}/runs/{run_id}/cancel — 202; graceful (FR-ASYNC-009).
### GET /api/v1/evaluations — paged list (filter by project/status).

---

## 9. Experiments, Comparison, Baselines

### POST /api/v1/experiments
- Request `{"project_id","dataset_version_id","model_id","model_version","prompt_version_id","parameters":{},"environment"}` → 201 experiment.
### GET /api/v1/experiments — paged. ### GET /api/v1/experiments/{id} — detail.
### POST /api/v1/experiments/{id}/run — 202 (async), idempotent.
### GET /api/v1/experiments/compare?ids=a,b,c — 200 side-by-side metrics table (FR-BENCH-001..004, §32).
### POST /api/v1/experiments/{id}/baseline
- `{"label":"Model A baseline"}` → 201 baseline (FR-REGRESSION-004; §102 Step 13). Idempotent per (project, experiment).

---

## 10. Prompts

| Method | Path | Roles |
|--------|------|-------|
| POST/GET | /api/v1/prompts | A, PO, E (create); all (view) |
| GET | /api/v1/prompts/{id} | all |
| POST | /api/v1/prompts/{id}/versions | A, PO, E — creates version (§33) |
| GET | /api/v1/prompts/{id}/versions | all |

---

## 11. Regression & Quality Gate

### POST /api/v1/regression/run
| Field | Value |
|-------|-------|
| Request | `{"project_id":"..","baseline_experiment_id":"..","candidate_experiment_id":".."}` |
| Response | 200 `{"run_id":"..","verdict":"pass|warning|regression_detected","deltas":{"accuracy":-0.05,"hallucination":0.05,"p95_latency_ms":120,"cost_per_request":0.002},"threshold_policy":{...}}` (§36–§37) |
| Roles | A, PO, E |
### GET /api/v1/regression/runs/{id} — 200.
### GET/PATCH /api/v1/projects/{id}/quality-gate — view/configure gate thresholds (§39; A, PO).

---

## 12. Observability, Traces, Metrics

### GET /api/v1/metrics
- Query: `?project_id=&scope=&range=15m|1h|24h|7d|30d|custom&from=&to=` (§41)
- Response: `{"requests":n,"errors":n,"error_rate":..,"latency":{"p50":..,"p95":..,"p99":..},"tokens":{...},"cost":..,"quality_score":..,"hallucination":..,"safety":..,"model_distribution":{...}}`
### GET /api/v1/projects/{id}/traces — paged (filter `?status=`,`?from=`,`?to=`).
### GET /api/v1/traces/{id} — trace + ordered events (§42; redacted per project settings, FR-OBS-007).
### POST /api/v1/projects/{id}/traces/ingest — **server-to-server** (org API key, `model` scope); body: request_id, model_ref, prompt_ref, started_at, duration_ms, token_usage, cost, status, error, steps[] (§13, §42). Rate limited (`model` scope). Accepts batch up to 100.

---

## 13. Alerts

| Method | Path | Roles |
|--------|------|-------|
| POST/GET | /api/v1/projects/{id}/alert-rules | A, PO (create); all (view) |
| GET/PATCH/DELETE | /api/v1/alert-rules/{id} | A, PO |
| GET | /api/v1/projects/{id}/alerts | all (feed, paged) |

**Rule body:** `{"type":"latency","severity":"warning","operator":"gt","threshold":3000,"duration_seconds":600,"cooldown_seconds":3600,"channel":"in_app","enabled":true}` (§43–§44).

---

## 14. Reports & Export

### POST /api/v1/reports
- `{"project_id","evaluation_run_id"|"experiment_id","format":"markdown|pdf|json|csv"}` → 202 `{"report_id","status":"queued","poll":...}` (§80).
### GET /api/v1/reports/{id} — metadata; `artifact_ref` presigned URL when ready.
### POST /api/v1/export
- `{"project_id","kind":"test_results|evaluation_results|metrics|experiment_results|research_data","format":"csv|json|markdown|pdf","filters":{}}` → 202 (§79).

---

## 15. Research

| Method | Path | Roles |
|--------|------|-------|
| POST/GET | /api/v1/research/projects | A, PO, E |
| GET/PATCH | /api/v1/research/projects/{id} | A, PO, E |
| POST/GET | /api/v1/research/projects/{id}/experiments | A, PO, E |
| GET | /api/v1/research/experiments/{id} | all |
| GET | /api/v1/research/experiments/{id}/statistics | all — mean/median/std/percentiles/CI/effect size (§48) |
| GET | /api/v1/research/experiments/{id}/publication | all — reproducibility metadata (§81) |

---

## 16. Admin, Audit, Settings, API Keys

| Method | Path | Roles |
|--------|------|-------|
| GET | /api/v1/audit-logs | A (paged, filters) |
| GET/PATCH | /api/v1/settings | A (org settings + privacy toggles §60) |
| POST | /api/v1/organizations/{id}/api-keys | A — 201 returns key **once** (prefix + secret); never again (AC-SEC-003) |
| GET | /api/v1/organizations/{id}/api-keys | A — metadata only (no secret) |
| DELETE | /api/v1/organizations/{id}/api-keys/{key_id} | A — 204 revoke |

---

## 17. Streaming

### GET /api/v1/stream
- SSE (text/event-stream), cookie or Bearer auth.
- Events: `evaluation.progress`, `evaluation.completed`, `evaluation.failed`, `alert.fired`, `notification`, `metric.rollup`.
- Frame: `event: <type>\ndata: <json>\n\n`. Filters by `?org_id=&project_id=`.

---

## 18. Pagination & List Contract

```
Request:  GET /api/v1/projects?limit=50&cursor=<opaque>
Response: {"items":[...],"next_cursor":"<opaque|null>"}
```
Cursor is opaque, server-encoded (UUID + sort key). `limit` 1–100 (default 25). All list endpoints return `X-Total-Count` (cheap count when enabled).

## 19. Common Response Envelope (non-list)

- `2xx`: resource JSON directly.
- `202`: job/run resource with `poll` link.
- `4xx/5xx`: [`ERROR_CONTRACTS.md`](./ERROR_CONTRACTS.md) envelope.

---

## 20. PRD Traceability (API)

| PRD §51 endpoint | Contract |
|------------------|----------|
| POST/GET /api/v1/projects, GET /projects/{id} | §4 ✅ |
| POST/GET /api/v1/datasets, POST /datasets/{id}/versions | §6 ✅ |
| POST /api/v1/evaluations, GET /evaluations/{id}, POST /evaluations/{id}/run | §8 ✅ |
| POST/GET /api/v1/experiments | §9 ✅ |
| POST/GET /api/v1/models | §5 ✅ |
| POST /api/v1/tests/generate | §7 ✅ |
| GET /api/v1/metrics | §12 ✅ |
| POST /api/v1/regression/run | §11 ✅ |
| GET /api/v1/reports/{id} | §14 ✅ |
| /health /ready /live (§65) | §1 ✅ |
| Consistent error format (§63) | ERROR_CONTRACTS ✅ |
| OpenAPI docs (§95) | Generated from these contracts ✅ |
| AC-CICD-001..005 (CI trigger/result/exit/dataset pin) | §8 run + `triggered_by=ci` + §11 gate ✅ |
