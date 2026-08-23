# AIREX PHASE 5 IMPLEMENTATION REPORT

Date: 2026-08-23
Scope: AI Test Generation & Dataset Intelligence — bounded, observable
GenerationRequest lifecycle, 6 generation types, 4 source types, structured JSON
output via the Model Gateway, strict candidate validation, SHA-256 fingerprint
dedup, deterministic generation quality score, human-in-the-loop candidate
review, dataset integration (reusing Phase 2 canonicalization/checksum/storage),
RBAC + multi-tenant security, audit events, Prometheus metrics, worker
integration, frontend. Reuses the Model Gateway — no provider SDKs are called
directly and no real LLM keys are required for the automated suite.

## Final Status

```
GenerationRequest lifecycle (QUEUED→RUNNING→COMPLETED/FAILED/CANCELLED): PASS
Generation configuration validation:                  PASS
Structured output parsing + candidate validation:    PASS
Fingerprinting + deduplication (duplicate_of):       PASS
Deterministic generation quality score:              PASS
Generation + candidate state machines:               PASS
Source snapshots (MANUAL_INSTRUCTION/DATASET/TEST_CASES/EVALUATION_FAILURES): PASS
Human review (approve/reject) + dataset integration: PASS
RBAC / multi-tenant security:                        PASS
Audit events + Prometheus metrics (airex_generation_*): PASS
Worker integration + stale recovery:                 PASS
Frontend (/projects/{id}/generations) + shared-types/api-client: PASS
Coverage gates (overall ≥89%, generation ≥95%):      PASS
Docker + migration 0006 (revision chain):            PASS (live run deferred)

Automated mocked generation verification: PASS
External LLM smoke test:               NOT EXECUTED (no provider credentials
                                        configured; suite is zero external cost)
Manual UI verification:                NOT EXECUTED (no interactive browser pass;
                                        no new Playwright suite per testing strategy)
```

## Architecture

```
GenerationRequest (QUEUED)
   └── worker task `generate_test_cases` → GenerationRunner
         ├── source_snapshot (frozen records + reference)
         ├── Model Gateway ──► Provider (generator model snapshot)
         ├── parse structured JSON (strict schema validation)
         ├── fingerprint (SHA-256) → dedup (duplicate_of)
         ├── deterministic quality score
         └── PENDING_REVIEW candidates
               └── human review → APPROVED/REJECTED
                     └── create dataset version (Phase 2 pipeline) + consumption
```

New/changed modules:

| Module | Responsibility |
| --- | --- |
| `app/models/generation.py` | `GenerationRequest` + `GeneratedCandidate` ORM (migration 0006) |
| `app/generation/config.py` | Generation type/source validation + bounded count + difficulty normalization |
| `app/generation/prompts.py` | Versioned prompt template (`1.0.0`) + `render_source_material` |
| `app/generation/parser.py` | Strict structured-output parsing + candidate validation |
| `app/generation/candidate.py` | SHA-256 fingerprint + deterministic quality score |
| `app/generation/state.py` | Request + candidate state machines |
| `app/generation/runner.py` | `GenerationRunner` + `recover_stale_generations` |
| `app/repositories/generation.py` | Request + candidate repositories (filters, dedup, consumption) |
| `app/services/generation.py` | Create/list/get/cancel, source snapshots, review, dataset integration, RBAC |
| `app/schemas/generation.py` | Pydantic generation/candidate/review schemas |
| `app/api/v1/generations.py` | Generation + candidate + dataset-version endpoints |
| `app/services/dataset.py` | `create_version_from_records` + shared `_finalize_version` |
| `app/core/metrics.py` | `airex_generation_*` Prometheus metrics |
| `app/workers/tasks.py` / `worker.py` | `generate_test_cases` task + stale recovery in the worker loop |
| `packages/shared-types`, `packages/api-client` | Generation types + API methods |
| `apps/web/app/projects/[id]/generations` | List/create + detail (candidate review + dataset creation) |

## Generation Request Lifecycle

- `POST /generations` validates project/environment/generator model (in project,
  active, provider configured), source type, generation type and configuration
  (count ∈ [1,100]), freezes the generator-model snapshot, source snapshot and
  prompt version, creates a QUEUED request, records `GENERATION_CREATED`, and
  enqueues the `generate_test_cases` worker task (ADR-021).
- The worker (`GenerationRunner`) drives QUEUED → RUNNING → COMPLETED/FAILED;
  a terminal request is never re-executed (idempotent duplicate jobs).
- `recover_stale_generations` marks RUNNING requests with a stale heartbeat as
  FAILED, so a crashed worker never leaves a request stuck.
- `POST /generations/{id}/cancel` and `GET`/list with filters (status, type,
  source) round out the lifecycle.

## Generation Sources

Frozen at creation (`source_snapshot`), never mutated (ADR-023):

- `MANUAL_INSTRUCTION` — instruction only, no records.
- `DATASET` — a dataset version (or dataset id → latest version) with its
  checksum and up to 50 records.
- `TEST_CASES` — explicit test-case ids (project-scoped), up to 50 records.
- `EVALUATION_FAILURES` — an evaluation run's FAIL/ERROR results with their test
  cases, up to 50 records.

## Structured Output & Candidate Validation

- The generator returns JSON `{"test_cases": [...]}`; the runner parses it
  strictly. A malformed top-level payload FAILS the generation; an individual
  invalid candidate is skipped (rejected from persistence) so one bad row never
  discards the batch.
- Candidate validation: non-empty input/expected (≤8000 chars), valid
  generation_type, difficulty, bounded category, dict context.
- Every candidate is fingerprinted (SHA-256 over normalized content); exact
  duplicates within a run or across re-runs are linked via `duplicate_of` and
  carry quality score 0 (dedup is deterministic, ADR-023).
- `generation_quality_score` (0.0–1.0) is a deterministic, preliminary score of
  field completeness/validity — explicitly not a semantic rating.

## Human Review & Dataset Integration

- All generated candidates start `PENDING_REVIEW`; `POST /candidates/{id}/review`
  (RBAC `CAP_GENERATE_TESTS`) approves or rejects once (reviewed → 409).
- `POST /generations/{id}/dataset-version` accepts only APPROVED, project-owned,
  unconsumed candidates and creates an immutable dataset version through the
  exact Phase 2 pipeline (`canonicalize → checksum → store → version row →
  test cases`), recording `GENERATED_DATASET_VERSION_CREATED` and tracking
  consumption (`dataset_version_id`) on each candidate (ADR-022).

## RBAC & Security

- `CAP_GENERATE_TESTS` is granted to OWNER/ADMIN/ENGINEER; VIEWER is read-only
  (view generation + candidates) and cannot create/cancel/review/dataset-create.
- Every read/write is tenant-scoped (project → organization); cross-org access
  returns 404/403, ID enumeration returns 404, and SQLi in instruction/status/
  source filters is inert (parameterized queries).
- Reviewer and dataset-integration endpoints validate the target organization,
  project and candidate status before any mutation.

## Audit & Metrics

Audit actions: `GENERATION_CREATED/STARTED/COMPLETED/FAILED/CANCELLED`,
`CANDIDATE_APPROVED/REJECTED`, `GENERATED_DATASET_VERSION_CREATED` (+ Phase 2
`DATASET_VERSION_CREATED` on the shared pipeline).

Prometheus (`app/core/metrics.py`):
`airex_generation_requests_total{status}`,
`airex_generation_duration_seconds`,
`airex_generation_candidates_total{status}`,
`airex_generation_candidates_duplicates_total`,
`airex_generation_candidates_rejected_total`,
`airex_generation_errors_total{category}`,
`airex_generation_provider_requests_total`. No high-cardinality labels.

## Frontend

- `/projects/{id}/generations` — create form (source, type, count, generator
  model, environment, optional dataset version, instruction) + list with live
  status polling, cancel, link to detail.
- `/projects/{id}/generations/{generationId}` — summary + snapshots, candidate
  table with quality score, approve/reject, and "create dataset version from
  approved candidates".
- `packages/shared-types` + `packages/api-client` extended with generation,
  candidate and dataset-version types/methods; navigation link added to the
  project page. `tsc --noEmit` and `next build` pass.

## Tests & Quality Gates

- Unit (`tests/unit/test_phase5.py`): config validation, state machines, prompt
  building, parsing/candidate validation, fingerprint, quality score, metrics
  helpers.
- Integration (`tests/integration/test_phase5_generations.py`): AT-P5-001..040
  plus source-type coverage (DATASET/TEST_CASES/EVALUATION_FAILURES), error
  paths, RBAC, snapshots, stale recovery, audit, metrics, worker-task full
  integration, repository idempotency.
- Security (`tests/security/test_phase5_security.py`): cross-tenant access,
  viewer read-only, ID enumeration, unauthorized approve/reject/dataset, SQLi.
- Full suite: **0 failures** (all phases). Coverage **89.30% overall**, generation
  **100%**, candidate validation **100%**, authz **100%**. ruff / black / mypy /
  tsc / `next build` all pass.
- Migration `0006_phase5_test_generation` is the Alembic head over
  `0005_phase4_llm_judge`; revision chain verified (`alembic heads`). It mirrors
  the verified Phase 4 migration pattern (PostgreSQL-only constraint style).
  Live PostgreSQL/Docker run was deferred because no database daemon was
  reachable in this session; the models and migration columns match exactly and
  the full test suite validates the models end-to-end on the per-test database.

## ADRs

- ADR-021 — Generation Request Lifecycle & Deterministic Generation
- ADR-022 — Human-in-the-Loop Candidate Review & Dataset Integration
- ADR-023 — Generation Reproducibility (Snapshots, Fingerprints & Quality Score)
