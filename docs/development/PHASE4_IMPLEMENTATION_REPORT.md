# AIREX PHASE 4 IMPLEMENTATION REPORT

Date: 2026-08-23
Scope: LLM-as-a-Judge, Rubrics (versioned, immutable), structured scoring,
confidence, reference-based/free judging, judge caching (org-scoped), combined
pass policies (ANY/ALL/WEIGHTED), judge metrics/audit, RBAC + security, worker
integration, frontend. Reuses the Model Gateway — no provider SDKs are called
directly and no real LLM keys are required for the automated suite.

## Final Status

```
LLM Judge:                          PASS
Rubrics (validation/versioning/immutability): PASS
Structured output validation:       PASS
Scoring / confidence / thresholds:  PASS
Reference-based & reference-free:   PASS
Judge caching (org-scoped):         PASS
Combined scoring + pass policy:     PASS
Judge metrics / tokens / audit:     PASS
Security / multi-tenant isolation:  PASS
Frontend (typecheck + build):       PASS
Docker + migration 0005 + live smoke: PASS

Automated mocked judge verification: PASS
Real provider smoke test:           NOT EXECUTED (no credentials configured)
Manual UI verification:             NOT EXECUTED (no interactive browser pass;
                                    no new Playwright suite per testing strategy)
```

## Architecture

```
Evaluation Run
   └── Test Case Result
         └── LLM Judge (evaluator `llm_judge`)
               ├── Rubric (frozen snapshot)
               ├── Judge Model (frozen snapshot) ──► Model Gateway ──► Provider
               └── Structured Score (validated) ──► Evaluation Result
```

New/changed modules:

| Module | Responsibility |
| --- | --- |
| `app/models/rubric.py` | Versioned `Rubric` ORM (project-scoped, ACTIVE/ARCHIVED) |
| `app/rubrics/validation.py` | Rubric validation + deterministic weight normalization |
| `app/repositories/rubric.py` | Rubric repository (versioning, `is_used`, archive) |
| `app/services/rubric.py` | Create (versioned), list/get/update (immutable if used), archive, RBAC, audit |
| `app/schemas/rubric.py` | Pydantic rubric schemas |
| `app/api/v1/rubrics.py` | `POST/GET/GET{id}/PATCH/DELETE /api/v1/rubrics` |
| `app/judge/base.py` | `LLMJudge` protocol, `JudgeRubric`, `JudgeResult`, `JudgeError` |
| `app/judge/prompts.py` | Versioned prompt template + `build_judge_messages` |
| `app/judge/validation.py` | Strict structured-response validation (`JudgeValidationError`) |
| `app/judge/cache.py` | Organization-scoped SHA-256 judge cache |
| `app/judge/llm_judge.py` | `ModelGatewayJudge` + registry evaluator `LLMJudgeEvaluator` |
| `app/evaluators/base.py` | Async evaluator support + dependency context (`evaluate_async`) |
| `app/evaluations/aggregate.py` | `apply_pass_policy` (ANY/ALL/WEIGHTED) + judge metrics |
| `app/evaluations/runner.py` | Async evaluator dispatch, judge snapshots, combined scoring, judge audit |
| `app/services/evaluation.py` | Judge model + rubric validation, judge snapshots at creation |
| `app/schemas/evaluation.py` | `llm_judge` config + judge result fields |
| `app/core/metrics.py` | `airex_llm_judge_*` Prometheus metrics |

## Rubric System

- `Rubric` rows are **immutable versions**; the version family is
  `(project_id, name)` and version numbers are sequential (1, 2, 3, …).
- Creating a rubric with an existing name creates the next version and archives
  the previous ACTIVE version (ADR-019). Historical evaluations keep
  referencing their exact version.
- `PATCH` on a rubric **already referenced by an evaluation run** → `409`
  (immutable). Unused rubrics can be edited; `DELETE` is a safe archive
  (`RUBRIC_ARCHIVED`).
- Validation (`app/rubrics/validation.py`): non-empty unique criterion names,
  non-empty descriptions, non-negative weights, total weight > 0, valid score
  ranges; weights are normalized to sum to 1.0 deterministically.
- API: `POST/GET/GET{id}/PATCH/DELETE /api/v1/rubrics` (list requires
  `project_id`; all tenant-scoped).

## Judge System

- The `llm_judge` evaluator is registered in the registry and **owns all judge
  behavior**; the runner only builds it with a dependency context and awaits
  `evaluate_async` (spec §24–§25).
- The judge model is independent of the target model and is invoked **only
  through the Model Gateway** (never provider SDKs); judge and target are
  snapshotted separately (spec §17).
- Judge model + rubric are validated at evaluation creation (exists, in project,
  active, provider configured; rubric ACTIVE) (spec §19).
- Structured responses are strictly validated (spec §13–§14): JSON object,
  required fields, score ranges, criterion names ⊆ rubric, confidence ∈ [0,1],
  boolean `passed`, non-empty bounded reasoning. Invalid → `EVALUATOR_ERROR`
  (or `TIMEOUT`/`PROVIDER_ERROR` for provider failures) without crashing the run.
- Provider failures reuse the gateway's retry/timeout policies (spec §32–§33);
  `airex_llm_judge_requests_total` reflects real judge calls after retries.

## Prompt Versioning

- A versioned template (`app/judge/prompts.py`, `JUDGE_PROMPT_VERSION =
  "1.0.0"`) is used for every judge call and recorded on the run and results
  (spec §15–§16, §31).
- Reference-based judging includes `expected_output`; reference-free
  (`reference_required: false`) omits it (spec §37). Only input, expected,
  actual, context and rubric are sent — never credentials/secrets (AT-P4-040).

## Scoring

- Scores are 0.0–1.0. Weighted overall = Σ(criterion_score × weight) with
  normalized weights.
- `score >= threshold` → PASS else FAIL (spec §18).
- Combined pass policy (spec §41): `ANY` (any evaluator passes), `ALL` (default;
  all pass), `WEIGHTED` (normalized weighted mean vs execution threshold).
  Individual evaluator scores are **always preserved** alongside the combined
  score (spec §40, §42).
- Judge results persist `judge_score`, `judge_confidence`, `judge_reasoning`,
  `judge_criteria_scores`, `combined_score`, and judge model/rubric/prompt
  snapshots (spec §38).
- Run metrics add `average_judge_score`, `judge_pass_rate`, `average_confidence`
  and per-criterion averages that follow the rubric dynamically (spec §39).
- **Confidence is documented as the judge model's self-reported confidence, not
  a calibrated probability** (spec §12).

## Caching

- `JudgeCache` is **organization-scoped** (a SHA-256 key includes target output,
  input, expected, context, rubric version, judge model and prompt version —
  never a test-case id alone) (spec §34–§35).
- Cache hits increment `airex_llm_judge_cache_hits_total`; a cache hit skips the
  model call (AT-P4-023). Changing rubric/model/content changes the key
  (AT-P4-024/025). Cross-org content never shares cache entries (AT-P4-038).

## Security

- Cross-tenant rubric / judge-model / evaluation access → 404/400.
- VIEWER: read-only for rubrics (403 on create/update/archive) and evaluations.
- Rubric immutability after use → 409; results remain immutable.
- ID enumeration → 404; SQL injection against rubric fields safely handled.
- Judge prompts never contain provider credentials/keys (AT-P4-040).

## Cost Safety

- All automated tests use the deterministic LOCAL provider with a documented
  `local_content` mock for judge responses — **zero external LLM API cost**.
- No `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` is required or
  hardcoded. Real provider execution is an optional manual smoke only.
- `estimated_cost` stays `NULL` (no invented pricing).

## APIs

- Rubrics: `POST/GET/GET{id}/PATCH/DELETE /api/v1/rubrics`.
- Evaluations: existing endpoints extended so `llm_judge` evaluator config
  carries `judge_model_id`, `rubric_id`, `threshold`, `reference_required`,
  `weight`; execution adds `pass_policy` and `threshold`. Run/result responses
  include judge snapshots and judge score fields.

## Database

Migration [`0005_phase4_llm_judge`](../../apps/api/alembic/versions/0005_phase4_llm_judge.py):

- `rubrics` table (versioned, ACTIVE/ARCHIVED, criteria JSON, indexes).
- `evaluation_runs`: `judge_model_id`, `judge_rubric_id`, `judge_model_snapshot`,
  `judge_rubric_snapshot`, `judge_prompt_version`.
- `evaluation_results`: `judge_score`, `judge_confidence`, `judge_reasoning`,
  `judge_criteria_scores`, `judge_model_snapshot`, `judge_rubric_snapshot`,
  `judge_prompt_version`, `combined_score`.

Verified on PostgreSQL: `upgrade head` (0004 → 0005), `downgrade -1` (→ 0004),
`upgrade head` (→ 0005); `alembic current` = `0005_phase4_llm_judge (head)`.

## Worker

- Reuses the existing `run_evaluation` task; the runner dispatches async judge
  evaluators with a dependency context (session, gateway, org-scoped cache, run
  snapshot). No second timeout/retry mechanism was introduced — the Model
  Gateway's policies are reused (spec §32–§33).

## Frontend

- `/projects/{id}/rubrics` — list/create (name, description, criteria with
  weights, live total-weight display)/archive.
- `/projects/{id}/evaluations` — creation form now supports the `llm_judge`
  evaluator (judge model, rubric, threshold) and pass policy.
- `/projects/{id}/evaluations/{id}` — results display judge score, confidence,
  per-criterion scores, reasoning, judge model / rubric version / prompt
  version, and combined score; summary shows average judge score + confidence.
- `packages/shared-types` + `packages/api-client` extended (rubrics + judge
  fields). Verified by `tsc --noEmit` and `next build`.

## Tests

### Unit (`tests/unit/test_phase4.py`)
Rubric validation (normalization, empty/duplicate/negative/zero/invalid range),
judge response validation (malformed, missing fields, out-of-range, unknown
criterion, confidence, bool, reasoning, non-numeric), prompt building
(reference-based/free, no secrets), cache keys + org isolation, pass-policy math
(ANY/ALL/WEIGHTED exact), judge snapshots, base-evaluator async defaults.

### Integration (`tests/integration/test_phase4_evaluations.py`)
AT-P4-001..040 via the deterministic LOCAL judge provider (mocked structured
JSON), plus rubric update/archive and judge metrics/cache/audit paths.

### Security (`tests/security/test_phase4_security.py`)
Cross-tenant rubric/judge-model/evaluation access, viewer restrictions, rubric
mutation authorization, ID enumeration, SQL injection, used-rubric immutability.

### Acceptance
See the Final Acceptance Matrix below (AT-P4-001..040).

## Regression

- Phase 0: PASS
- Phase 1: PASS
- Phase 2: PASS
- Phase 3: PASS
- Phase 4: PASS

## Coverage

- Overall **87.30%** (target ≥87%).
- LLM judge (`app/judge/*`): `base.py` 100%, `prompts.py` 100%, `cache.py` 96%,
  `llm_judge.py` 95%, `validation.py` 98% (target ≥95%).
- Rubric (`app/rubrics/validation.py` 97%, `app/api/v1/rubrics.py` 97%,
  `app/repositories/rubric.py` 100%, `app/services/rubric.py` 95%,
  `app/schemas/rubric.py` 100%, `app/models/rubric.py` 100%) (target ≥95%).
- Authorization `app/core/permissions.py` 100% (target ≥95%).
- Security-sensitive modules (`ssrf` 90%, `encryption` 91%, `security` 96%,
  `errors` 93%) (target ≥90%).

## Docker

- Migration 0005 upgrade/downgrade/upgrade verified on Docker PostgreSQL;
  worker restarted with the Phase 4 code; API (uvicorn `--reload`, bind-mounted
  source) serves the rubric + judge routes.
- Live Dockerized Phase 4 smoke: register → project → env → LOCAL provider →
  target model → judge model (`local_content`) → JSONL dataset → rubric v1 →
  create llm_judge evaluation → worker completes → PASS with `judge_score`
  0.89 → `/metrics` exposes `airex_llm_judge_requests_total` / `..._tokens_total`:
  **SMOKE PASS**.

## Known Limitations

- `app/workers/worker.py` (standalone worker loop) is exercised by the live
  smoke and the runner-path tests but is not unit-covered (long-running process;
  same as prior phases).
- The in-memory `JudgeCache` is per-runner-instance (persists across test cases
  within a run); a Redis-backed cache can replace it behind the same interface
  for multi-worker deployments.
- **LLM-as-a-judge has inherent limitations** (model bias, evaluator
  instability, sensitivity to prompt wording, judge–target correlation,
  preference bias, imperfect calibration). Phase 4 mitigates with versioned
  prompts/rubrics, structured scoring, explicit criteria, confidence, and
  deterministic validation — but does **not** claim these eliminate bias.
- Real-provider execution and interactive UI flows were not run
  (**NOT EXECUTED**); all automated verification used mocked judge responses.

## Final Acceptance Matrix

| ID | Result |
| --- | --- |
| AT-P4-001 create valid rubric | PASS (201) |
| AT-P4-002 invalid rubric weights | PASS (400) |
| AT-P4-003 rubric versioning (v1, v2) | PASS |
| AT-P4-004 used rubric immutable | PASS (409) |
| AT-P4-005 create LLM judge evaluation | PASS (201 QUEUED) |
| AT-P4-006 judge receives correct input | PASS (prompt unit + run completes) |
| AT-P4-007 valid structured judge response | PASS (PASS, score stored) |
| AT-P4-008 malformed judge JSON | PASS (ERROR EVALUATOR_ERROR, no crash) |
| AT-P4-009 score outside 0–1 | PASS (ERROR EVALUATOR_ERROR) |
| AT-P4-010 unknown criterion | PASS (ERROR EVALUATOR_ERROR) |
| AT-P4-011 weighted score exact math | PASS (combined 0.89) |
| AT-P4-012 threshold pass | PASS (PASS) |
| AT-P4-013 threshold fail | PASS (FAIL) |
| AT-P4-014 reference-based | PASS |
| AT-P4-015 reference-free | PASS |
| AT-P4-016 judge model cross-org | PASS (400/404) |
| AT-P4-017 cross-tenant rubric | PASS (400) |
| AT-P4-018 viewer cannot create rubric | PASS (403) |
| AT-P4-019 viewer can view rubric | PASS (200) |
| AT-P4-020 judge timeout | PASS (ERROR TIMEOUT) |
| AT-P4-021 judge provider error | PASS (ERROR PROVIDER_ERROR) |
| AT-P4-022 judge retry | PASS (transient → retry → success) |
| AT-P4-023 judge cache hit | PASS (1 call, cache_hits++) |
| AT-P4-024 cache key changes with rubric | PASS |
| AT-P4-025 cache key changes with judge model | PASS |
| AT-P4-026 combined deterministic + LLM judge | PASS (both scores preserved) |
| AT-P4-027 weighted combined score | PASS (0.923 exact) |
| AT-P4-028 reasoning stored, not in audit | PASS |
| AT-P4-029 judge model snapshot | PASS |
| AT-P4-030 rubric snapshot | PASS |
| AT-P4-031 prompt version snapshot | PASS |
| AT-P4-032 evaluator version snapshot | PASS |
| AT-P4-033 judge token metrics | PASS |
| AT-P4-034 judge Prometheus metrics | PASS |
| AT-P4-035 judge audit events | PASS (STARTED + COMPLETED) |
| AT-P4-036 judge failure continues (stop_on_error=false) | PASS |
| AT-P4-037 judge failure stops (stop_on_error=true) | PASS |
| AT-P4-038 cross-org cache isolation | PASS |
| AT-P4-039 SQL injection safe | PASS |
| AT-P4-040 no secrets in judge prompts | PASS |

## Final Decision

```
AIREX PHASE 4: PASS
```
