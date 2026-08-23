# ADR-023: Generation Reproducibility — Snapshots, Fingerprints & Quality Score

- Status: Accepted
- Date: 2026-08-23
- Phase: 5
- Deciders: AIREX Engineering
- Related: ADR-017 (evaluation reproducibility), ADR-020 (judge reproducibility), ADR-021 (generation lifecycle), ADR-014 (canonicalization)

## Context

Generated test cases must be auditable: given a `GenerationRequest`, anyone
should be able to reconstruct exactly what was generated, why, from which source
material, and with which generator model — even months later when prompts,
models and source data have changed.

## Decision

### Frozen snapshots (never mutated after creation)

At creation every request freezes:

- `generator_model_snapshot` — provider type/id, model identifier, effective
  configuration, base URL, temperature/max_tokens/top_p, model version.
- `source_snapshot` — the source type, its reference (dataset version + checksum,
  test-case ids, or evaluation run) and the source records (capped at 50).
- `prompt_version` — the versioned generation prompt template (`1.0.0`).
- `configuration` — normalized count, generation types and difficulty weights.

The runner executes **against these snapshots**, never the live rows.

### Deterministic deduplication

Each candidate stores a SHA-256 `fingerprint` over normalized
input/expected/context. The same content always yields the same fingerprint, so:

- within a run, exact duplicates are linked via `duplicate_of`;
- across runs, re-running the same request never creates duplicate rows
  (idempotency at the row level).

### Deterministic generation quality score

`generation_quality_score` (0.0–1.0) is a **preliminary, deterministic** score of
field completeness and validity (input/expected length, category, difficulty,
duplicate penalty) — it is explicitly NOT a semantic/AI quality rating. It is
computed locally so it is cheap, reproducible and stable across runs.

## Consequences

- Historical generations are fully reconstructable (same snapshot ⇒ same prompt
  ⇒ same candidates, modulo generator nondeterminism).
- Dedup is deterministic and cross-run safe.
- The quality score is a stable, honest signal — never a claim of semantic
  correctness.
- Extends the ADR-017/ADR-020 reproducibility model to the generation path.
