# ADR-019: Rubric Versioning & Immutability

- Status: Accepted
- Date: 2026-08-23
- Phase: 4
- Deciders: AIREX Engineering
- Related: ADR-018 (llm judge), ADR-020 (judge reproducibility), ADR-012 (dataset versioning)

## Context

Rubrics define how a judge scores outputs. A rubric that changes over time would
silently change the meaning of historical evaluation results, so scoring rules
must be frozen per evaluation.

## Decision

- A **rubric row is a single immutable version**. The version family is
  `(project_id, name)` and version numbers are sequential (1, 2, 3, …).
- Creating a rubric with an existing name creates the **next version** and
  archives the previous ACTIVE version. Historical evaluations keep referencing
  the exact version they used.
- **Once a version is referenced by an evaluation run it can never be mutated**
  (`PATCH` → `409`). Unused versions may still be edited. `DELETE` is a safe
  archive (`RUBRIC_ARCHIVED`) — nothing is hard-deleted.
- Criteria are validated and weights normalized to sum to 1.0 deterministically
  (`app/rubrics/validation.py`); invalid criteria are rejected at the API.
- Rubric status is `ACTIVE`/`ARCHIVED`.

## Consequences

- Evaluation results remain interpretable: the rubric version is part of the run
  snapshot (ADR-020).
- "Editing" a used rubric means creating a new version — an explicit, audited
  act.
- Enforces the same immutability philosophy as dataset versions (ADR-012).
