# AIREX Phase 2 — Dataset Management, Versioning & Test Cases

Date: 2026-08-22
Scope: Dataset Management, Dataset Versioning, Test Case Management, Dataset
Import (CSV/JSON/JSONL), Dataset Validation, Dataset Export.

Phase 0 and Phase 1 remain the source of truth; this phase extends the existing
Phase 0 dataset tables and adds the Phase 2 lifecycle/import/export surface.

---

## 1. Architecture

```
Project
   │
   └── Dataset (ACTIVE/ARCHIVED)
         │
         └── DatasetVersion (immutable snapshot: v1, v2, v3, ...)
               │
               └── Test Cases (content-immutable; status PENDING/APPROVED/REJECTED/ARCHIVED)
```

New backend modules:

| Module | Responsibility |
| --- | --- |
| `app/models/dataset.py` | Extended `Dataset`/`DatasetVersion`/`TestCase` ORM |
| `app/datasets/parsers.py` | CSV / JSON / JSONL parsing (format errors) |
| `app/datasets/validation.py` | Record validation (required fields, limits, duplicates) |
| `app/datasets/canonical.py` | Deterministic canonicalization + SHA-256 checksum |
| `app/storage.py` | `StorageProvider` protocol + `LocalStorageProvider` |
| `app/repositories/dataset.py` | Dataset/version/test-case repositories (tenant-scoped) |
| `app/services/dataset.py` | Lifecycle, import, immutable versioning, export, test-case status |
| `app/schemas/dataset.py` | Pydantic schemas |
| `app/api/v1/datasets.py` | REST endpoints (replaces the Phase 1 dataset stub) |

## 2. Database changes

Migration [`0003_phase2_datasets`](../../apps/api/alembic/versions/0003_phase2_datasets.py)
extends the existing Phase 0 tables (no tables recreated):

- `datasets`: added `status` (ACTIVE/ARCHIVED + CHECK) and `metadata` (JSON).
- `dataset_versions`: added `status` (UPLOADING/VALIDATING/PROCESSING/COMPLETED/
  FAILED + CHECK), `format` (csv/json/jsonl), and an index on `checksum`. The
  existing unique constraint `(dataset_id, version_number)` is retained.
- `test_cases`: added `row_number` (source ordering) and indexes on `status` and
  `category`.

Verified on PostgreSQL: `upgrade head` (0002 → 0003), `downgrade -1` (→ 0002),
`upgrade head` (→ 0003), `alembic current` = `0003_phase2_datasets (head)`.

## 3. Dataset lifecycle

- `POST /api/v1/projects/{project_id}/datasets` → 201 (AT-P2-001)
- `GET  /api/v1/projects/{project_id}/datasets` (paginated; name, description,
  latest_version, record_count, version_count, status) (AT-P2-002)
- `GET  /api/v1/datasets/{dataset_id}` (AT-P2-003)
- `PATCH /api/v1/datasets/{dataset_id}` (name/description/metadata/status only;
  never project/organization) (AT-P2-004)
- `DELETE /api/v1/datasets/{dataset_id}` → **safe archive** (status=ARCHIVED);
  versions remain readable (AT-P2-005)

## 4. Versioning model (immutable & reproducible)

- `POST /api/v1/datasets/{dataset_id}/versions` — multipart upload
  (`file` + optional `format`); creates the next sequential version (AT-P2-006,
  AT-P2-007, AT-P2-008).
- `GET /api/v1/datasets/{dataset_id}/versions` (paginated)
- `GET /api/v1/dataset-versions/{version_id}`
- `PATCH /api/v1/dataset-versions/{version_id}` → `409 DATASET_VERSION_IMMUTABLE`
  (AT-P2-021)
- Per-dataset sequential numbering via `(dataset_id, version_number)` unique
  constraint + a retry-on-conflict import; concurrent imports always yield
  distinct numbers (verified).
- Version fields (`version_number`, `checksum`, `record_count`,
  `storage_reference`, test-case membership) are never mutated after creation.
  Test cases are content-immutable; only status may change (approve/reject).

## 5. Storage model

- `StorageProvider` protocol (`put/get/delete/exists`); `LocalStorageProvider`
  under configurable `DATASET_STORAGE_DIR`.
- Keys are generated: `datasets/{dataset_id}/versions/{n}/dataset.jsonl`; never
  derived from user filenames. Filenames with traversal segments or absolute
  paths are rejected (AT-P2-033). S3 can be added later behind the protocol.

## 6. Checksum algorithm

Documented in [ADR-014](ADR-014-dataset-canonicalization.md). Deterministic
canonical JSONL (source order, fixed field set, sorted keys, ASCII-escaped) →
SHA-256 hex stored on `dataset_versions.checksum`. Same canonical content ⇒ same
checksum (AT-P2-020); import → export → re-canonicalize ⇒ equal checksum
(AT-P2-029). The stored artifact IS the canonical JSONL; JSONL/JSON exports are
checksum-preserving (CSV is for human use and may not round-trip nested context).

## 7. Validation rules

- Errors (version cannot be created): empty `input`, empty `expected_output`,
  record count > `DATASET_MAX_RECORDS`, unsupported format
  (`INVALID_DATASET_FORMAT`), malformed JSON/CSV/JSONL (JSONL reports the line
  number), invalid UTF-8 (`INVALID_DATASET_ENCODING`), file > `DATASET_MAX_FILE_SIZE_MB`
  (`413 DATASET_TOO_LARGE`).
- Warnings (version may still be created): duplicate `input` (`DUPLICATE_INPUT`).
- Import is atomic: parse → validate → canonicalize → checksum → store → DB
  transaction. A failed import leaves no official partial version (AT-P2-034).

## 8. API endpoints (all tenant-scoped)

- Datasets: create/list/get/update/archive (above).
- Versions: create/list/get/export.
- Test cases: list (page/page_size/search/category/status/difficulty), get,
  approve, reject; `PATCH /test-cases/{id}` → `409 DATASET_VERSION_IMMUTABLE`.
- `GET /api/v1/dataset-versions/{version_id}/export?format=jsonl|json|csv`
  (download; audited `DATASET_VERSION_EXPORT`).

## 9. Security

- Organization/project isolation enforced in the service for datasets, versions
  and test cases (cross-org returns 404; AT-P2-030..032).
- RBAC: create/update/archive/import/approve/reject require `manage_datasets`
  (OWNER/ADMIN/ENGINEER); viewers can read only (403 on mutations).
- File security: size limits, filename safety (path traversal/absolute rejected),
  format whitelist, malformed content, invalid encoding.
- Audit events: `DATASET_CREATED`, `DATASET_UPDATED`, `DATASET_ARCHIVED`,
  `DATASET_VERSION_CREATED`, `DATASET_VERSION_EXPORT`, `TEST_CASE_APPROVED`,
  `TEST_CASE_REJECTED` — never dataset contents.

## 10. Error codes

`DATASET_NOT_FOUND`, `DATASET_ARCHIVED`, `DATASET_VERSION_NOT_FOUND`,
`DATASET_VERSION_IMMUTABLE`, `INVALID_DATASET_FORMAT`, `INVALID_DATASET_SCHEMA`,
`DATASET_TOO_LARGE` (413), `TOO_MANY_RECORDS`, `INVALID_DATASET_ENCODING`,
`DUPLICATE_DATASET_VERSION`, `INVALID_TEST_CASE` (see `app/core/errors.py`).

## 11. Frontend

- `/projects/{id}/datasets` — list, create, open, archive.
- `/projects/{id}/datasets/{datasetId}` — details, import (file + format) with
  validation-error display, version list (created/records/checksum/status) with
  export, test-case list with search + category/status filters, pagination and
  approve/reject (mutation controls hidden for immutable content — there is no
  content-edit control).
- Project page now links to Datasets.
- `packages/shared-types` + `packages/api-client` extended (incl. multipart upload
  and blob export).
- Manual verification recommended for interactive flows; no new Playwright suite
  was added (per Phase 2 testing strategy).

## 12. Tests

- Unit (`tests/unit/test_datasets.py`): CSV/JSON/JSONL parsers, validation,
  canonicalization, checksum, storage round-trip + traversal, filename
  sanitization.
- Integration/acceptance (`tests/integration/test_datasets_api.py`):
  AT-P2-001..036 + concurrency + viewer restrictions + targeted service coverage.
- Security (`tests/security/test_phase2_security.py`): SQL injection (name +
  search), path traversal, cross-tenant dataset/version/test-case isolation,
  cross-org project, viewer read-only, oversized upload, invalid format, malformed
  file.

## 13. Acceptance criteria (executed)

| ID | Result |
| --- | --- |
| AT-P2-001 create dataset | PASS (201) |
| AT-P2-002 list datasets | PASS (200, paginated) |
| AT-P2-003 get dataset details | PASS (200) |
| AT-P2-004 update metadata | PASS (200) |
| AT-P2-005 archive | PASS (ARCHIVED) |
| AT-P2-006 CSV → v1 | PASS |
| AT-P2-007 second version → v2 | PASS |
| AT-P2-008 separate dataset → v1 | PASS |
| AT-P2-009 duplicate version number | PASS (unique constraint blocks; 409 path) |
| AT-P2-010 malformed CSV | PASS (400) |
| AT-P2-011 malformed JSON | PASS (400) |
| AT-P2-012 malformed JSONL w/ line | PASS (400, line reported) |
| AT-P2-013 missing input | PASS (validation error) |
| AT-P2-014 missing expected_output | PASS (validation error) |
| AT-P2-015 empty input | PASS (validation error) |
| AT-P2-016 invalid UTF-8 | PASS (400 INVALID_DATASET_ENCODING) |
| AT-P2-017 oversized file | PASS (413 DATASET_TOO_LARGE) |
| AT-P2-018 record limit | PASS (TOO_MANY_RECORDS) |
| AT-P2-019 checksum exists | PASS (SHA-256) |
| AT-P2-020 same content → same checksum | PASS |
| AT-P2-021 version immutable | PASS (409 DATASET_VERSION_IMMUTABLE) |
| AT-P2-022 test cases linked to correct version | PASS |
| AT-P2-023 test-case pagination | PASS |
| AT-P2-024 test-case search | PASS |
| AT-P2-025 status filter | PASS |
| AT-P2-026 approve + audit | PASS |
| AT-P2-027 reject + audit | PASS |
| AT-P2-028 export | PASS |
| AT-P2-029 export checksum == original | PASS (jsonl + json) |
| AT-P2-030 cross-org dataset | PASS (404) |
| AT-P2-031 cross-org version | PASS (404) |
| AT-P2-032 cross-org test case | PASS (404) |
| AT-P2-033 path traversal filename | PASS (rejected) |
| AT-P2-034 failed import no partial version | PASS |
| AT-P2-035 archive prevents new versions | PASS (409 DATASET_ARCHIVED) |
| AT-P2-036 version history intact | PASS (v1 unchanged, v2 created) |

## 14. Regression & quality gates

- Backend: **209 tests, 0 failed, 0 errors** (Phase 0 + Phase 1 + Phase 2).
- Coverage: overall **83.48%** (target ≥82%); dataset modules:
  `app/datasets/validation.py` 100%, `canonical.py` 100%, `parsers.py` 95%,
  `app/storage.py` 93%, `app/services/dataset.py` 96%, `app/repositories/dataset.py`
  100%, `app/models/dataset.py` 100% (target ≥90%); authorization
  `app/core/permissions.py` 100% (target ≥95%); security modules ≥90%.
- Quality gates: ruff **PASS**, black --check **PASS**, mypy **PASS** (82 files),
  `tsc --noEmit` **PASS**, `next build` **PASS** (11 pages).

## 15. Docker / migration verification

- Migration 0003 upgrade/downgrade/upgrade verified on Docker PostgreSQL;
  `alembic current` = `0003_phase2_datasets (head)`.
- `docker compose build` (api, worker, web) + `up -d`: all 7 services up;
  api/postgres/redis/worker healthy, web ready; `/health /live /ready /metrics`
  → 200.
- Live Dockerized end-to-end smoke: register → project → dataset → upload (v1,
  checksum) → versions → test-cases → export 200 — all PASS.

## 16. Known limitations

- CSV export is provided for human use; it may not round-trip nested `context`
  exactly (JSONL/JSON are the canonical checksum-preserving exports).
- The test-case "edit" story is intentionally create-a-new-version (no in-place
  mutation); the UI offers no content-edit control for immutable versions.
- A new Playwright suite was intentionally NOT created (Phase 2 testing strategy);
  the Phase 1 E2E specs remain as regression evidence.

## 17. Final status

```
PHASE 2 STATUS

Dataset Management:  PASS
Dataset Versioning:  PASS
Import:              PASS
Validation:          PASS
Test Cases:          PASS
Export:              PASS
Security:            PASS
Phase 1 Regression:  PASS
Backend:             PASS
Frontend:            PASS
Docker:              PASS

Overall:
PHASE 2: PASS
```
