# ADR-013: Dataset Artifact Storage

- Status: Accepted
- Date: 2026-08-22
- Phase: 2
- Deciders: AIREX Engineering
- Related: ADR-012 (versioning), ADR-014 (canonicalization)

## Context

Imported datasets are stored as an immutable artifact (canonical JSONL). Storing
potentially large files directly in PostgreSQL rows is undesirable; a storage
abstraction keeps the database lean and lets production use object storage later.

## Decision

- Introduce a minimal `StorageProvider` protocol with `put`, `get`, `delete`,
  `exists` in [`app/storage.py`](../../apps/api/app/storage.py).
- Ship `LocalStorageProvider`, backed by a configurable directory
  (`DATASET_STORAGE_DIR`); S3 can be added later behind the same protocol without
  changing callers.
- Storage keys are **generated identifiers only**:
  `datasets/{dataset_id}/versions/{version_number}/dataset.jsonl`. User-supplied
  filenames are never used to construct storage paths.
- `storage_reference` on `dataset_versions` points to that generated key; arbitrary
  filesystem paths are never exposed to clients.
- Filenames are validated: traversal segments (`..`) and absolute paths are
  rejected (`400 INVALID_DATASET_SCHEMA`).

## Consequences

- Large artifacts stay out of PostgreSQL; only the reference + checksum + metadata
  live in the database.
- Path traversal and filename injection are prevented by construction.
- Adding S3 later is a drop-in implementation of the same protocol.
