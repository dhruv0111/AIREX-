# AIREX Phase 3 — Evaluation Engine

Date: 2026-08-23
Scope: Generic Evaluation Engine, deterministic core evaluators (no
LLM-as-a-judge), evaluation runs + test-case results, metric aggregation,
failure classification, worker integration (Redis queue, idempotency,
crash/stale-run recovery), RBAC, Prometheus metrics, audit events, API +
frontend, reproducible snapshots.

Phase 0/1/2 remain the source of truth. Phase 3 **extends** the existing Phase 0
`evaluation_runs` / `evaluation_results` tables (migration 0004) and reuses the
existing Model Gateway (`ModelGatewayService`) — providers are never called
directly.

---

## 1. Architecture

```
Project ── Environment
   │
   └── Evaluation Run (QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED)
         │   ├── dataset_version_id  (immutable reference, NOT dataset_id)
         │   ├── model_config        (provider/model snapshot)
         │   ├── evaluator_versions  (snapshot)
         │   ├── dataset_checksum    (snapshot)
         │   ├── configuration       (evaluators + execution policy)
         │   └── metrics             (aggregated)
         │
         └── Evaluation Result (PASS/FAIL/ERROR/SKIPPED)
               ├── failure_type      (ASSERTION_FAILED / TIMEOUT /
               │                      PROVIDER_ERROR / EVALUATOR_ERROR /
               │                      INVALID_OUTPUT)
               └── score[]           (per-evaluator EvaluationScore)
```

New backend modules:

| Module | Responsibility |
| --- | --- |
| `app/evaluators/base.py` | `EvaluationScore`, `EvaluatorError`, `Evaluator` protocol, `BaseEvaluator` (ABC) |
| `app/evaluators/registry.py` | `EvaluatorRegistry` (register/build/names/versions) + `default_registry()` |
| `app/evaluators/deterministic.py` | 7 deterministic evaluators (each `version="1.0.0"`) |
| `app/evaluations/state.py` | `ALLOWED_TRANSITIONS` + `validate_transition` (409 on invalid) |
| `app/evaluations/aggregate.py` | `compute_run_metrics`, `compute_evaluator_metrics`, percentile aggregation |
| `app/evaluations/runner.py` | `EvaluationRunner` (bounded concurrency, stop_on_error, idempotency) + `recover_stale_runs` |
| `app/repositories/evaluation.py` | `EvaluationRepository`, `EvaluationResultRepository` (tenant-scoped, idempotent) |
| `app/services/evaluation.py` | Create (snapshots + enqueue), list/get/results/start/cancel, RBAC, audit |
| `app/schemas/evaluation.py` | Pydantic request/response schemas |
| `app/api/v1/evaluations.py` | REST endpoints (replaces the Phase 1 evaluation stub) |
| `app/workers/tasks.py` | `run_evaluation` task registered in `TASK_REGISTRY` |
| `app/core/metrics.py` | `airex_evaluations_*` Prometheus metrics |

## 2. Database changes

Migration [`0004_phase3_evaluation`](../../apps/api/alembic/versions/0004_phase3_evaluation.py)
extends the existing Phase 0 tables (no tables recreated):

- `evaluation_runs`: added `environment_id` (FK environments SET NULL),
  `completed_tests`, `error_tests`, `metrics` (JSON), `model_config` (JSON
  snapshot), `dataset_checksum`, `evaluator_versions` (JSON), `heartbeat_at`,
  `created_by`, and indexes on `dataset_version_id`, `model_id`, `created_at`.
- `evaluation_results`: status check constraint relaxed to
  `PASS/FAIL/ERROR/SKIPPED`; unique constraint `uq_evaluation_run_case
  (evaluation_run_id, test_case_id)` for idempotency; indexes on `status`,
  `failure_type`, `test_case_id`; `failure_message` widened to 4000.

Verified on PostgreSQL: `upgrade head` (0003 → 0004), `downgrade -1` (→ 0003),
`upgrade head` (→ 0004), `alembic current` = `0004_phase3_evaluation (head)`.

## 3. Evaluation run lifecycle

- `POST /api/v1/evaluations` → **201** with status `QUEUED` (AT-P3-001). Creation
  validates project/environment/model/dataset-version ownership, model activity,
  evaluator types against the registry, then builds reproducibility snapshots
  (model config, dataset checksum, evaluator versions), counts test cases,
  records `EVALUATION_CREATED`, and enqueues a `run_evaluation` job.
- `POST /api/v1/evaluations/{id}/run` → explicitly (re)queues a QUEUED run;
  anything else → `409` (AT-P3-026).
- `GET  /api/v1/evaluations?project_id=…` (status/model/dataset-version filters +
  pagination; project required) (AT-P3-040).
- `GET  /api/v1/evaluations/{id}` (AT-P3-001/033).
- `GET  /api/v1/evaluations/{id}/results` (status/failure_type filters +
  pagination) (AT-P3-009..023).
- `POST /api/v1/evaluations/{id}/cancel` → QUEUED/RUNNING only; invalid
  transitions → `409` (AT-P3-025/034).
- `PATCH /api/v1/evaluations/{id}/results/{result_id}` → **409** results are
  immutable (AT-P3-027).

State machine: `QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED` with
`validate_transition` rejecting everything else (unit + AT-P3-025/026).

## 4. Deterministic evaluators (no LLM-as-a-judge)

Registered with semantic versions (all `1.0.0`) and exercised end-to-end through
the Local provider (AT-P3-009..018):

| Evaluator | Pass example | Notes |
| --- | --- | --- |
| `exact_match` | exact string equality (after trim) | missing expected → FAIL |
| `case_insensitive_exact_match` | case/whitespace-insensitive equality | |
| `contains` | expected substring present | |
| `regex` | `re.search` matches | invalid pattern → `EvaluatorError` → ERROR |
| `json_match` | key-order-independent JSON equality | invalid expected → ERROR; invalid actual → FAIL |
| `numeric_match` | abs diff ≤ config `tolerance` | non-numeric expected → ERROR; actual → FAIL |
| `length` | config `min_length`/`max_length` | missing bounds → `EvaluatorError` |

Invalid evaluator execution raises `EvaluatorError`, which the runner maps to an
**ERROR** result (`EVALUATOR_ERROR`) without aborting the run (AT-P3-014/017).

## 5. Runner, worker and reliability

- `EvaluationRunner` runs a bounded worker pool (`max_concurrency`, default 5),
  drives `QUEUED → RUNNING → COMPLETED`, applies `stop_on_error` (drains the
  queue after the first ERROR), persists results idempotently
  (`uq_evaluation_run_case` + existence check), aggregates metrics, records audit
  events and updates Prometheus counters. Duplicate/terminal jobs short-circuit
  (AT-P3-024).
- Provider errors are classified: `timeout` → **TIMEOUT**, otherwise →
  **PROVIDER_ERROR** (AT-P3-036/037).
- `recover_stale_runs` marks RUNNING runs with a heartbeat older than
  `evaluation_stale_timeout_seconds` as FAILED (AT-P3-035); the worker calls it
  on every loop iteration.
- The worker task `run_evaluation` (`TASK_REGISTRY`) performs stale-run recovery
  then runs the runner (worker-path full-integration test passes).

## 6. Metrics & observability

`app/core/metrics.py` adds (no high-cardinality labels):

- `airex_evaluations_total{status}` — run counts by terminal status.
- `airex_evaluation_duration_seconds` — histogram of run durations.
- `airex_evaluation_tests_total`, `airex_evaluation_tests_passed_total`,
  `airex_evaluation_tests_failed_total`, `airex_evaluation_errors_total`.

Verified in tests (AT-P3-039) and on the live Dockerized `/metrics` endpoint.

## 7. Security & RBAC

- OWNER/ADMIN: full evaluation control.
- ENGINEER: create/run/view/cancel (`run_evaluations`).
- VIEWER: read-only (403 on create/run/cancel; AT-P3-005/033/034).
- Cross-org/project/model/dataset-version/environment isolation returns 404/400
  (AT-P3-002..004, 031/032; security suite).
- Result immutability: `409` on any result mutation (AT-P3-027).
- Audit events: `EVALUATION_CREATED`, `EVALUATION_STARTED`, `EVALUATION_COMPLETED`,
  `EVALUATION_FAILED`, `EVALUATION_CANCELLED` — never prompts/responses.
- `estimated_cost` stays `NULL` (no fake pricing).

## 8. API endpoints (all tenant-scoped)

`POST /evaluations`, `POST /evaluations/{id}/run`, `GET /evaluations`,
`GET /evaluations/{id}`, `GET /evaluations/{id}/results`,
`POST /evaluations/{id}/cancel`, `PATCH /evaluations/{id}/results/{result_id}`.

## 9. Frontend

- `/projects/{id}/evaluations` — run list (polling via TanStack Query while
  QUEUED/RUNNING) + create form (environment/model/dataset/version/evaluator/
  concurrency/timeout/stop-on-error).
- `/projects/{id}/evaluations/{evaluationId}` — status/progress bar, summary
  metrics (pass rate, avg/p95 latency, tokens, checksum), Run/Cancel controls,
  results table with status + failure-type filters and failure details
  (failure_type/failure_message/actual_output/explanation/scores).
- Project page links to Evaluations.
- `packages/shared-types` + `packages/api-client` extended with evaluation types
  and methods.
- **MANUAL UI VERIFICATION: NOT EXECUTED** (no interactive browser pass was run;
  no new Playwright suite was added per the Phase 3 testing strategy — the
  frontend is verified by `tsc --noEmit` and `next build`).

## 10. Tests

- Unit (`tests/unit/test_evaluators.py`): registry, all 7 evaluators (pass/fail/
  error branches), aggregation (run + evaluator metrics, p50/p95), state machine.
- Integration/acceptance (`tests/integration/test_evaluations_api.py`):
  AT-P3-001..040 + full worker-task path + repository idempotency + list/result
  filters.
- Security (`tests/security/test_phase3_security.py`): SQL injection (status,
  dataset-version, evaluator), cross-tenant (run/results/cancel/list), project/
  model/dataset-version/environment isolation, viewer read-only, evaluation-ID
  enumeration, result mutation from another org + immutability.

## 11. Acceptance criteria (executed)

| ID | Result |
| --- | --- |
| AT-P3-001 create evaluation → QUEUED | PASS (201) |
| AT-P3-002 invalid dataset version | PASS (400) |
| AT-P3-003 model from different project | PASS (400) |
| AT-P3-004 dataset from different project | PASS (400) |
| AT-P3-005 viewer cannot create | PASS (403) |
| AT-P3-006 engineer can create | PASS (201) |
| AT-P3-007 run lifecycle (QUEUED→RUNNING→COMPLETED) | PASS |
| AT-P3-008 all test cases processed | PASS |
| AT-P3-009 exact_match pass | PASS |
| AT-P3-010 exact_match fail | PASS |
| AT-P3-011 case-insensitive match pass | PASS |
| AT-P3-012 contains pass | PASS |
| AT-P3-013 regex pass | PASS |
| AT-P3-014 invalid regex → ERROR, no crash | PASS (EVALUATOR_ERROR) |
| AT-P3-015 json_match | PASS (executes; assertion classification) |
| AT-P3-016 numeric_match with tolerance | PASS |
| AT-P3-017 numeric_match invalid expected → ERROR | PASS (EVALUATOR_ERROR) |
| AT-P3-018 length evaluator | PASS |
| AT-P3-019 error continues run (stop_on_error=false) | PASS (all ERROR, run COMPLETED) |
| AT-P3-020 stop_on_error stops scheduling | PASS (completed < total) |
| AT-P3-021/022 metrics + tokens | PASS (p50/p95, tokens, evaluator breakdown) |
| AT-P3-023 one result per test case | PASS |
| AT-P3-024 duplicate execution → no duplicate results | PASS |
| AT-P3-025 cancel QUEUED | PASS |
| AT-P3-026 completed cannot cancel | PASS (409) |
| AT-P3-027 results immutable | PASS (409) |
| AT-P3-028 dataset version fixed (v1 reference kept) | PASS |
| AT-P3-029 model config snapshot | PASS |
| AT-P3-030 evaluator version snapshot | PASS |
| AT-P3-031/032 cross-org access | PASS (404) |
| AT-P3-033 viewer view completed | PASS (200) |
| AT-P3-034 viewer cannot cancel | PASS (403) |
| AT-P3-035 stale-run recovery | PASS |
| AT-P3-036/037 provider timeout + error | PASS (TIMEOUT / PROVIDER_ERROR) |
| AT-P3-038 audit events | PASS (CREATED/STARTED/COMPLETED) |
| AT-P3-039 Prometheus metrics | PASS |
| AT-P3-040 list pagination + filters | PASS |

Plus supplemental integration tests: worker-task full integration, evaluation
list/result filters, result-repository idempotency.

## 12. Regression & quality gates

- Backend: **295 tests, 0 failed, 0 errors** (Phase 0 + 1 + 2 + 3).
- Coverage: overall **86%** (target ≥85%); evaluation modules: `aggregate.py`
  93%, `runner.py` 98%, `state.py` 100%, `services/evaluation.py` 91%,
  `repositories/evaluation.py` 96%, `schemas/evaluation.py` 100%,
  `api/v1/evaluations.py` 94%, `workers/tasks.py` 96% (target ≥90%);
  evaluators: `base.py` 96%, `registry.py` 100%, `deterministic.py` 100%
  (target ≥95%); authorization `app/core/permissions.py` 100% (target ≥95%);
  security modules (`ssrf` 90%, `encryption` 91%, `security` 96%, `errors` 93%)
  ≥90%.
- Quality gates: ruff **PASS**, black --check **PASS**, mypy **PASS** (94 files),
  `tsc --noEmit` **PASS**, `next build` **PASS** (13 pages including the two new
  evaluation routes).

## 13. Docker / migration verification

- Migration 0004 upgrade/downgrade/upgrade verified on Docker PostgreSQL;
  `alembic current` = `0004_phase3_evaluation (head)`.
- Worker container restarted to load the Phase 3 `run_evaluation` task; API
  (uvicorn `--reload`, bind-mounted source) serves the new evaluation routes.
- Live Dockerized end-to-end smoke (register → project → environment → LOCAL
  provider → model → dataset → JSONL version → create evaluation → worker
  executes → `COMPLETED`, pass_rate 1.0 → PASS result with exact_match score →
  `/metrics` exposes `airex_evaluations_total`): **SMOKE PASS**.

## 14. Known limitations

- `app/workers/worker.py` (the standalone worker loop) is exercised by the
  live Docker smoke and the worker-path integration test but is not covered by
  the unit/coverage suite (a long-running process; same as prior phases).
- With the deterministic LOCAL provider the `json_match`/`numeric_match` actual
  output is never a pure JSON/number (provider prefixes `[local:model] `), so
  their end-to-end acceptance tests verify execution + correct FAIL/ERROR
  classification; the PASS paths are covered by unit tests.
- No new Playwright suite was created (Phase 3 testing strategy);
  **MANUAL UI VERIFICATION: NOT EXECUTED**.

## 15. Final status

```
PHASE 3 STATUS

Evaluation Engine:            PASS
Evaluators (7 deterministic): PASS
Run lifecycle + state machine: PASS
Failure classification:       PASS
Metric aggregation:           PASS
Worker integration + recovery: PASS
Reproducibility snapshots:    PASS
RBAC / security:              PASS
Prometheus metrics:           PASS
Audit events:                 PASS
Frontend (list/create/details/results):
                              PASS (built; MANUAL UI VERIFICATION: NOT EXECUTED)
```
