# ADR-014: Deterministic Dataset Canonicalization & Checksum

- Status: Accepted
- Date: 2026-08-22
- Phase: 2
- Deciders: AIREX Engineering
- Related: ADR-012 (versioning), ADR-013 (storage)

## Context

Every dataset version must carry a deterministic SHA-256 checksum so the same
canonical content always produces the same digest, and so `import → version →
export → canonicalize → checksum` round-trips reproducibly (AT-P2-020, AT-P2-029).

## Decision

Canonicalization algorithm (implemented in
[`app/datasets/canonical.py`](../../apps/api/app/datasets/canonical.py)):

1. Keep records in their **source order** (preserved via `test_cases.row_number`).
2. Project each record onto the fixed canonical field set
   (`input, expected_output, context, category, difficulty, metadata`), dropping
   unknown keys and omitting `null` values.
3. Serialize each record as compact JSON with **sorted keys** and
   `ensure_ascii=True` (ASCII-escaped UTF-8 is byte-for-byte deterministic).
4. Join records with `\n` and append a trailing newline; encode UTF-8.

The checksum is `SHA-256(canonical_bytes)`, stored on `dataset_versions.checksum`.
The **stored artifact is exactly the canonical JSONL bytes**, and the JSONL export
returns those bytes unchanged; JSON export re-serializes the same parsed records
(checksum-preserving). CSV export is provided for human use and may not round-trip
nested `context` exactly.

Duplicate inputs are treated as a **warning** (validation does not fail); empty
`input`/`expected_output` are **errors** (the version is rejected).

## Consequences

- Identical canonical content yields identical checksums regardless of source
  format or key ordering.
- Exported versions can be re-imported with the same checksum.
- The checksum is a trustworthy artifact identity for future evaluation runs.
