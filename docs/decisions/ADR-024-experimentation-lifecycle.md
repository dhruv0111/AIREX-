# ADR-024: Experimentation Lifecycle — Variants, Runs & Async Execution

- Status: Accepted
- Date: 2026-08-25
- Phase: 6
- Deciders: AIREX Engineering
- Related: ADR-005 (Redis background jobs), ADR-015 (Evaluation engine), ADR-017 (Evaluation reproducibility)

## Context

To run reliable model/prompt benchmarking and comparisons, AIREX needs a way to define experiments comparing a baseline model/prompt config against a candidate model/prompt config over a target dataset version. 
This execution must be background-safe, concurrent, and fully reproducible even if global model/prompt configurations or datasets change over time.

## Decision

### Immutable Variant Freezing

At the creation of an `Experiment`, variant settings are frozen and stored as `ExperimentVariant` records. 
Each variant freezes:
- Model snapshot (identifier, provider configuration)
- Prompt version/template configuration
- Variant parameters (e.g. temperature, max tokens, custom JSON configuration)

This ensures variants cannot be mutated after the experiment is created, protecting the integrity of all future benchmarking runs.

### Experiment Run State Machine

Experiment execution runs through an `ExperimentRun` lifecycle:
`DRAFT` → `QUEUED` → `RUNNING` → `COMPLETED` / `FAILED` / `CANCELLED`

- **Concurrent Execution**: The background runner dispatches baseline and candidate evaluations concurrently using the existing `EvaluationRunner` orchestrations.
- **Synchronous Fallback**: For unit/integration tests and local environments lacking Redis queue managers, the runner executes evaluations synchronously in-process to prevent hanging.
- **Stale Run Recovery**: A stale heartbeat tracker automatically transitions stuck `RUNNING` experiment runs to `FAILED` if the runner goes offline.

## Consequences

- Full variant reproducibility is maintained across the lifecycle of the experiment.
- Experiment runs can execute concurrently without blocking the main API thread.
- Local development and test runs do not require external queue servers.
