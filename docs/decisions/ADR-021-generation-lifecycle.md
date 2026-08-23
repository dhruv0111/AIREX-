# ADR-021: Generation Request Lifecycle & Deterministic Generation

- Status: Accepted
- Date: 2026-08-23
- Phase: 5
- Deciders: AIREX Engineering
- Related: ADR-005 (background jobs), ADR-011 (model gateway), ADR-022 (candidate review), ADR-023 (generation reproducibility)

## Context

AI test generation produces large numbers of candidate test cases from an
LLM. Unbounded or ad-hoc generation is unmanageable: runs can be duplicated,
source material can drift, and there is no way to recover a crashed run. Phase 5
needs a first-class, observable generation request that is bounded, idempotent
and recoverable — mirroring the evaluation engine (Phase 3).

## Decision

A `GenerationRequest` row drives a strict state machine executed by the worker:

```
QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED
```

- **Bound**: `count` is validated to `[1, 100]` and `generation_types` /
  `difficulty_distribution` are normalized deterministically
  (`app.generation.config`).
- **Queue**: creation auto-enqueues the `generate_test_cases` worker task
  (Redis queue, in-memory for tests) — same pattern as evaluations.
- **Idempotent**: a terminal request is never re-executed; a duplicate job
  returns `{status, idempotent: true}`.
- **Recoverable**: `recover_stale_generations` marks RUNNING requests with a
  stale heartbeat as FAILED, so a crashed worker never leaves a request stuck
  RUNNING.
- **Sourced**: the request freezes a `source_snapshot` (records + reference) at
  creation for `MANUAL_INSTRUCTION | DATASET | TEST_CASES | EVALUATION_FAILURES`.
- **Fingerprint-dedup**: generated candidates are deduplicated by a SHA-256
  fingerprint (ADR-023), so re-runs never create duplicate rows.

## Consequences

- Generation is observable, bounded and restart-safe.
- Every request is reproducible from its frozen snapshots.
- Reuses the established queue / runner / stale-recovery infrastructure, keeping
  operational complexity low.
