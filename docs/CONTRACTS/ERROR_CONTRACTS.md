# Error Contracts — AIREX

Standardized error model mandated by PRD §63: every error is returned in a single envelope with `code`, `message`, `request_id`, and never exposes internal stack traces (SEC-ERR-002). This contract defines the envelope, the code taxonomy, HTTP mapping, per-endpoint error tables, and platform error surfaces (workers, gateway, webhooks).

---

## 1. Error Envelope (PRD §63)

```json
{
  "error": {
    "code": "EVALUATION_TIMEOUT",
    "message": "Evaluation exceeded configured timeout.",
    "request_id": "req_abc123"
  }
}
```

**Extended (optional, always present for validation & provider errors):**
```json
{
  "error": {
    "code": "DATASET_IMPORT_ROW_ERROR",
    "message": "3 rows failed to import.",
    "request_id": "req_abc123",
    "status": 400,
    "details": {
      "field_errors": [
        {"row": 12, "field": "input", "reason": "missing required field"}
      ],
      "retryable": false
    }
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | ✅ | Machine-readable code (see taxonomy) |
| `message` | string | ✅ | Human-readable, localized, no internals |
| `request_id` | string | ✅ | Echo of `X-Request-Id`; correlates with logs (SEC-LOG-001) |
| `status` | integer | optional | HTTP status (defaults to transport status) |
| `details` | object | optional | Structured context (field errors, retryable flag, provider code) |
| `retryable` | boolean (in details) | optional | For async/provider surfaces (§58) |

**Invariants:**
- No stack traces, no SQL, no internal hostnames, no secrets in any error payload (SEC-ERR-002).
- `request_id` is always present; server generates one if client omitted `X-Request-Id`.
- Errors logged (full detail incl. trace ID) server-side; only the envelope reaches clients.

---

## 2. HTTP Status → Code Families

| HTTP | Family | Notes |
|------|--------|-------|
| 400 | `VALIDATION_*` | Malformed request, schema violations, import row errors |
| 401 | `AUTH_*` | Missing/invalid/expired credentials; unauthenticated (AC-AUTH-004) |
| 403 | `AUTHZ_*` | Authenticated but not permitted (AC-AUTH-006, AC-SEC) |
| 404 | `NOT_FOUND_*` | Resource missing **or** cross-tenant (anti-enumeration, AC-SEC-002) |
| 409 | `CONFLICT_*` | State conflicts: duplicate email, duplicate dataset id, archived project, run in progress, immutability |
| 410 | `EXPIRED_*` | Expired one-time tokens (verification, password reset) |
| 422 | `EVALUATION_*` / `JOB_*` | Business-rule evaluation failures surfaced via API |
| 429 | `RATE_LIMIT_*` | Rate limiting (§62) |
| 5xx | `SERVER_*` / `MODEL_*` | Unexpected / normalized provider errors (AC-MODEL-004) |

---

## 3. Error Code Taxonomy (authoritative list)

### 3.1 Validation (400)
`VALIDATION_ERROR` · `VALIDATION_FIELD` · `DATASET_DUPLICATE_ID` · `DATASET_IMPORT_ROW_ERROR` · `DATASET_EMPTY` · `UPLOAD_TOO_LARGE` · `UPLOAD_BAD_FORMAT`

### 3.2 Auth (401)
`AUTH_MISSING_TOKEN` · `AUTH_INVALID_CREDENTIALS` (AC-AUTH-003) · `AUTH_TOKEN_EXPIRED` · `AUTH_TOKEN_REVOKED` · `AUTH_EMAIL_UNVERIFIED` · `AUTH_EMAIL_EXISTS` (AC-AUTH-002) · `AUTH_INVALID_TOKEN` · `AUTH_ACCOUNT_DISABLED`

### 3.3 Authorization (403 / 404)
`AUTHZ_FORBIDDEN` · `AUTHZ_ROLE_REQUIRED` (AC-AUTH-006) · `AUTHZ_CROSS_TENANT` (AC-SEC-001) · `AUTHZ_API_KEY_SCOPE` · `NOT_FOUND_*` (cross-tenant returns 404, AC-SEC-002)

### 3.4 Not found (404)
`NOT_FOUND_USER` · `NOT_FOUND_ORGANIZATION` · `NOT_FOUND_PROJECT` · `NOT_FOUND_MODEL` · `NOT_FOUND_DATASET` · `NOT_FOUND_DATASET_VERSION` · `NOT_FOUND_TEST` · `NOT_FOUND_EVALUATION` · `NOT_FOUND_RUN` · `NOT_FOUND_EXPERIMENT` · `NOT_FOUND_PROMPT` · `NOT_FOUND_REPORT` · `NOT_FOUND_TRACE` · `NOT_FOUND_ALERT_RULE` · `NOT_FOUND_RESOURCE` (generic)

### 3.5 Conflict (409)
`CONFLICT_EMAIL_EXISTS` · `CONFLICT_DATASET_ID` · `CONFLICT_ORGANIZATION_SLUG` · `CONFLICT_PROJECT_NAME` · `CONFLICT_ARCHIVED_PROJECT` (FR-PROJECT-005) · `CONFLICT_RUN_IN_PROGRESS` · `CONFLICT_EXPERIMENT_IMMUTABLE` (FR-EXPERIMENT-002) · `CONFLICT_DATASET_VERSION_IMMUTABLE` (BR-DATASET-002) · `CONFLICT_BASELINE_EXISTS` · `CONFLICT_API_KEY_SCOPE`

### 3.6 Expired (410)
`EXPIRED_VERIFICATION_TOKEN` · `EXPIRED_RESET_TOKEN`

### 3.7 Evaluation / job (422)
`EVALUATION_TIMEOUT` (PRD §63 example) · `EVALUATION_CANCELLED` · `EVALUATION_PROVIDER_ERROR` · `EVALUATION_INVALID_CONFIG` · `EVALUATION_NO_BASELINE` · `JOB_FAILED` · `JOB_NOT_FOUND` · `TEST_GENERATION_FAILED` · `REPORT_FAILED` · `EXPORT_FAILED`

### 3.8 Rate limit (429)
`RATE_LIMIT_API` · `RATE_LIMIT_EVALUATION` · `RATE_LIMIT_MODEL` · `RATE_LIMIT_DATASET_GENERATION` · `RATE_LIMIT_TEST_GENERATION` · `RATE_LIMIT_AUTH` (scopes per §62)

### 3.9 Model / provider (normalized, AC-MODEL-002..004)
`MODEL_PROVIDER_ERROR` · `MODEL_AUTH_ERROR` (AC-MODEL-002) · `MODEL_TIMEOUT` (AC-MODEL-003) · `MODEL_RATE_LIMITED` · `MODEL_CONTEXT_LENGTH` · `MODEL_UNAVAILABLE`

### 3.10 Server (5xx)
`SERVER_ERROR` · `SERVER_DATABASE_UNAVAILABLE` · `SERVER_REDIS_UNAVAILABLE` · `SERVER_STORAGE_UNAVAILABLE` · `SERVER_MAIL_UNAVAILABLE`

---

## 4. Per-Endpoint Error Matrix (key endpoints)

| Endpoint | Possible codes |
|----------|----------------|
| POST /auth/register | 400 VALIDATION_ERROR · 409 CONFLICT_EMAIL_EXISTS · 429 RATE_LIMIT_AUTH |
| POST /auth/login | 401 AUTH_INVALID_CREDENTIALS · 403 AUTH_EMAIL_UNVERIFIED · 429 RATE_LIMIT_AUTH |
| POST /projects | 400 VALIDATION_ERROR · 409 CONFLICT_PROJECT_NAME · 401 AUTH_* · 403 AUTHZ_ROLE_REQUIRED |
| GET /projects/{id} | 401 · 404 NOT_FOUND_PROJECT (also cross-tenant) |
| DELETE /projects/{id} | 400 VALIDATION_ERROR (missing confirm) · 404 NOT_FOUND_PROJECT · 403 AUTHZ_FORBIDDEN |
| POST /datasets | 409 CONFLICT_DATASET_ID · 400 VALIDATION_ERROR |
| POST /datasets/{id}/versions | 409 CONFLICT_ARCHIVED_PROJECT · 404 NOT_FOUND_DATASET · 409 CONFLICT_DATASET_VERSION_IMMUTABLE |
| POST /evaluations/{id}/run | 409 CONFLICT_ARCHIVED_PROJECT · 409 CONFLICT_RUN_IN_PROGRESS · 429 RATE_LIMIT_EVALUATION · 404 NOT_FOUND_EVALUATION |
| GET /evaluations/{id}/runs/{run_id} | 404 NOT_FOUND_RUN · 401 |
| POST /tests/generate | 429 RATE_LIMIT_TEST_GENERATION · 422 TEST_GENERATION_FAILED · 400 VALIDATION_ERROR |
| POST /regression/run | 422 EVALUATION_NO_BASELINE · 400 VALIDATION_ERROR · 404 |
| GET /metrics | 400 VALIDATION_ERROR (bad range) · 401 |
| POST /reports | 422 REPORT_FAILED · 400 VALIDATION_ERROR · 404 |
| POST /traces/ingest | 401 AUTH_INVALID_CREDENTIALS · 403 AUTHZ_API_KEY_SCOPE · 429 RATE_LIMIT_MODEL · 400 VALIDATION_ERROR |
| All | 500 SERVER_ERROR · 503 SERVER_*_UNAVAILABLE (health-gated) · 429 RATE_LIMIT_API |

---

## 5. Async Surface Errors

Job/run resources carry the error envelope in their `error` field:
```json
{"run_id":"..","status":"FAILED","error":{"code":"MODEL_TIMEOUT","message":"Provider timed out after 60s.","request_id":"req_..","details":{"retryable":true,"attempts":3,"max_retries":3}}}
```
- `details.retryable=true` ⇒ will be retried (transient, §58); `false` ⇒ permanent (no infinite retry).
- Evaluations surface a **summary** error; per-test failures are recorded on `test_results.status/error` (partial failure handling, §89).

## 6. Logging Correlation

| Error artifact | Contains |
|----------------|----------|
| Client envelope | code, message, request_id (no internals) |
| Server log | request_id, user_id, organization_id, service, level, message, trace_id, error detail, ip (SEC-LOG-001/002) |
| Audit | action=..., result=failure|denied, details (no secrets) |

---

## 7. PRD Traceability (ERROR)

| PRD requirement | Contract |
|-----------------|----------|
| §63 standard structure `{error:{code,message,request_id}}` | §1 envelope ✅ |
| §63 "must not expose internal stack traces" | §1 invariants ✅ |
| §51 "consistent error formats" | §2–§4 ✅ |
| AC-MODEL-002..004 (controlled/normalized provider errors) | §3.9 + §5 ✅ |
| §62 rate limiting (5 scopes, per-org configurable) | §3.8 + headers in API_CONTRACTS ✅ |
| SEC-LOG-001/002 (log fields, no secrets) | §6 ✅ |
| AC-SEC-002 (no project-ID bypass) | 404-not-found policy §3.3 ✅ |
