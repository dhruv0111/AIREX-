# ADR-022: Human-in-the-Loop Candidate Review & Dataset Integration

- Status: Accepted
- Date: 2026-08-23
- Phase: 5
- Deciders: AIREX Engineering
- Related: ADR-012 (dataset versioning), ADR-013 (dataset storage), ADR-014 (canonicalization), ADR-021 (generation lifecycle)

## Context

LLM-generated test cases are unverified by construction. Pushing them directly
into a dataset would poison the evaluation corpus and violate the immutability
guarantees of Phase 2 (ADR-012). Phase 5 needs a trusted bridge from
"machine-generated" to "part of a reproducible dataset".

## Decision

Generated candidates are **never trusted automatically**. Each candidate enters
as `PENDING_REVIEW` and only a human can transition it:

```
PENDING_REVIEW → APPROVED | REJECTED   (terminal, one-way)
```

- The runner persists every candidate (including deduplicated ones linked via
  `duplicate_of`) as `PENDING_REVIEW`; nothing is auto-approved.
- A `POST /candidates/{id}/review` endpoint (RBAC `CAP_GENERATE_TESTS`)
  approves or rejects; a reviewed candidate cannot be re-reviewed (409).
- **Dataset integration** (`POST /generations/{id}/dataset-version`) accepts
  only APPROVED candidates of the dataset's own project; each candidate may be
  consumed once (`dataset_version_id` tracks consumption; reuse → 400).
- The dataset version is created through the exact Phase 2 pipeline
  (`DatasetService.create_version_from_records`: validate → canonicalize →
  checksum → store → version row → test cases), preserving the reproducibility
  invariants of ADR-012/ADR-013/ADR-014.

## Consequences

- The evaluation corpus is only ever extended by human-reviewed, project-owned
  candidates.
- Approved candidates become immutable dataset versions indistinguishable from
  uploaded ones — same canonicalization, checksum and storage.
- Consumption tracking prevents double-adding the same candidate.
