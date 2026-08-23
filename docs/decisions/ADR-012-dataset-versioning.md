# ADR-012: Immutable Dataset Versioning

- Status: Accepted
- Date: 2026-08-22
- Phase: 2
- Deciders: AIREX Engineering
- Related: ADR-007 (multi-tenancy), ADR-013 (storage), ADR-014 (canonicalization)

## Context

AIREX will later run evaluations against datasets. For a future evaluation run
to be reproducible, the exact test cases, checksum and record count a run used
must be frozen at import time. A dataset is a logical container; a **dataset
version** is an immutable snapshot of test cases.

The Phase 0 schema already had `datasets`, `dataset_versions` and `test_cases`
tables (from the foundation), so Phase 2 **extends** those tables rather than
recreating them.

## Decision

- A dataset version is created only by import and, once committed, is **never
  mutated**: `version_number`, `checksum`, `record_count`, `storage_reference`,
  `format` and test-case membership are set at creation and immutable.
- Version numbers are **sequential per dataset** (1, 2, 3, ...), enforced by the
  unique constraint `(dataset_id, version_number)` and a retry-on-conflict import
  so concurrent imports cannot produce the same number.
- Test cases inside a version are **content-immutable**: `PATCH /test-cases/{id}`
  and `PATCH /dataset-versions/{id}` are rejected with `409 DATASET_VERSION_IMMUTABLE`.
  Only test-case **status** (PENDING → APPROVED/REJECTED) may change.
- To change content, the user creates a new version.
- Import is atomic: parse → validate → canonicalize → checksum → store → DB
  transaction. Any failure leaves **no** official partial version (a failed import
  never creates a version with 0 test cases).
- Archived datasets remain readable but cannot receive new versions.
- `DELETE /datasets/{id}` is implemented as a **safe archive** (historical data is
  never physically deleted by default).

## Consequences

- Evaluations can pin an exact version and trust that its test cases and checksum
  will never change (reproducibility guarantee).
- "Editing" requires creating a new version, which is an explicit, audited act.
- Duplicate/concurrent version creation is prevented by a DB constraint plus
  retry logic.
