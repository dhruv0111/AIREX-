# ADR-008: Experiment Immutability

**Status:** Accepted

## Context
Once an experiment completes, its configuration and results must remain reproducible (PRD §34–§35, §78). Never silently overwrite dataset/prompt/evaluation/model/evaluator versions.

## Decision
- Versioned entities (dataset_versions, prompt_versions, evaluators, evaluation_configs) are stored as immutable rows; runs reference **version rows**, not live tables.
- Completed experiments are write-protected by the service layer (and enforced by DB constraints in later migrations).
- Version snapshots (including checksums) are stored for reproducibility metadata.

## Alternatives
- Mutable experiment records — violates §34 and reproducibility (prohibited #8).
- Copy-on-write only — still allows accidental mutation of references.

## Consequences
- Pros: reproducible experiments, audit-friendly, matches §102 step 20.
- Cons: more version rows; queries must join to pinned versions.
