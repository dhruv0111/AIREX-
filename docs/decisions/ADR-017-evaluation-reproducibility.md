# ADR-017: Evaluation Reproducibility Snapshots

- Status: Accepted
- Date: 2026-08-23
- Phase: 3
- Deciders: AIREX Engineering
- Related: ADR-012 (dataset versioning), ADR-014 (dataset canonicalization), ADR-015 (evaluation engine), ADR-016 (deterministic evaluators)

## Context

An evaluation result is only meaningful if the exact inputs, model configuration,
dataset content and scoring logic used can be reconstructed later. Datasets and
models are mutable over time; an evaluation must not silently change meaning when
a dataset gains a new version or a model's settings change.

## Decision

At creation, every evaluation run freezes the following **immutable snapshots**
(stored on `evaluation_runs`, never mutated afterwards):

- **Dataset version** — `dataset_version_id` (a fixed, immutable reference per
  ADR-012) plus `dataset_checksum` (SHA-256 of the canonical content per
  ADR-014), so the exact test-case set is pinned.
- **Model configuration** — `model_config` JSON snapshot: `provider_id`,
  `provider_type`, `model_identifier`, `temperature`, `max_tokens`, `top_p`,
  `configuration`, `base_url`. Changing the live model later does not affect
  already-created runs.
- **Evaluation configuration** — the full `configuration` (evaluators +
  execution policy: `max_concurrency`, `timeout_seconds`, `stop_on_error`).
- **Evaluator versions** — `evaluator_versions` maps each evaluator name to its
  semantic version at run creation (ADR-016).

The runner executes against these snapshots, so a completed run is fully
reproducible: replaying the same dataset version, model snapshot, evaluator
versions and configuration reproduces the same results.

## Consequences

- Historical runs are auditable and reproducible without relying on current
  dataset/model state.
- Deleting or re-importing a dataset, or editing a model, never rewrites history.
- Snapshot fields are written once at creation and treated as immutable by the
  codebase and tests (AT-P3-028/029/030).
