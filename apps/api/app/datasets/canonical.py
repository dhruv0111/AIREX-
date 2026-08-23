"""Deterministic canonicalization + SHA-256 checksum (Phase 2 §32–§33, §40).

Canonicalization algorithm (documented; ADR-014):
1. Keep records in their source order (preserved by ``row_number``).
2. Project each record onto the fixed canonical field set, dropping unknown
   keys and omitting ``null`` values (so equivalent records canonicalize the
   same way).
3. Serialize each record as compact JSON with **sorted keys** and
   ``ensure_ascii=True`` (ASCII-escaped UTF-8 is fully deterministic).
4. Join the per-record lines with ``\\n`` and append a trailing newline.

The same dataset content therefore always produces the same checksum, and the
canonical JSONL artifact is exactly what is stored and exported, so
``import → version → export → canonicalize → checksum`` is reproducible.
"""

from __future__ import annotations

import hashlib
import json

_CANONICAL_FIELDS = ("input", "expected_output", "context", "category", "difficulty", "metadata")


def _normalize_record(record: dict) -> dict:
    normalized: dict = {}
    for field_name in _CANONICAL_FIELDS:
        value = record.get(field_name)
        if value is not None:
            normalized[field_name] = value
    return normalized


def canonicalize(records: list[dict]) -> bytes:
    """Return deterministic canonical JSONL bytes for ``records``."""
    lines: list[str] = []
    for record in records:
        normalized = _normalize_record(record)
        lines.append(
            json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def checksum(records: list[dict]) -> str:
    """SHA-256 hex digest of the canonical representation (Phase 2 §32)."""
    return hashlib.sha256(canonicalize(records)).hexdigest()
