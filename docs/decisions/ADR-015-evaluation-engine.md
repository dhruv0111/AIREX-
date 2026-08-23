# ADR-015: Generic Evaluation Engine

- Status: Accepted
- Date: 2026-08-23
- Phase: 3
- Deciders: AIREX Engineering
- Related: ADR-005 (redis background jobs), ADR-011 (model gateway), ADR-012 (dataset versioning), ADR-016 (deterministic evaluators), ADR-017 (reproducibility)

## Context

AIREX must evaluate model outputs against curated test cases. Evaluations are
long-running, potentially expensive, and must be reproducible. The Phase 0
schema already defined `evaluation_runs` and `evaluation_results` tables, and
the Model Gateway (`ModelGatewayService`) is the single entry point for model
calls. Phase 3 must turn those primitives into a working Evaluation Engine
without introducing a second model-call path.

## Decision

- **Reuse the Model Gateway.** The runner (`EvaluationRunner`) builds a
  `ModelRequest` from a frozen model-config snapshot and calls
  `ModelGatewayService.invoke(...)`; providers are never invoked directly.
- **Extend, do not recreate, the Phase 0 tables** via migration
  `0004_phase3_evaluation` (scoping, progress counters, snapshots, heartbeat,
  idempotency constraint).
- **Asynchronous execution on the worker** (Redis queue, ADR-005). Creating an
  evaluation returns `201 QUEUED` and enqueues a `run_evaluation` job. The
  worker drives `QUEUED → RUNNING → COMPLETED/FAILED`.
- **A run is scoped to** project + environment + model + dataset **version**
  (an immutable reference, never a mutable `dataset_id`).
- **Bounded concurrency** (configurable `evaluation_max_concurrency`, default 5),
  per-test `stop_on_error` semantics, and **crash/stale-run recovery** via a
  heartbeat that the worker reconciles on every loop.
- **Idempotency:** a `(evaluation_run_id, test_case_id)` unique constraint plus
  an existence check prevent duplicate results on job retries; duplicate jobs
  short-circuit at the runner.
- **Results are immutable** once a run is terminal (`409` on mutation).

## Consequences

- One model-call path (the Gateway) means consistent retries, error
  normalization, metrics and audit across invocations and evaluations.
- Evaluations are durable and recoverable; a crashed worker never leaves a run
  permanently RUNNING.
- Reproducibility is guaranteed by snapshotting (ADR-017).
- The engine is generic: new evaluation types (e.g. RAG in later phases) can
  reuse the same run/result lifecycle.
