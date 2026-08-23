"""Candidate fingerprinting, deduplication and quality scoring (Phase 5)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.generation.config import DIFFICULTIES


def normalize_text(value: str | None) -> str:
    """Normalize whitespace/line endings for a deterministic fingerprint."""
    return " ".join(str(value or "").split())


def fingerprint_candidate(
    *, input_text: str, expected_output: str | None, context: dict[str, Any] | None
) -> str:
    """Deterministic SHA-256 fingerprint over normalized content."""
    payload = json.dumps(
        {
            "input": normalize_text(input_text),
            "expected_output": normalize_text(expected_output),
            "context": (
                json.dumps(context, sort_keys=True, default=str, ensure_ascii=True)
                if context
                else None
            ),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_quality_score(candidate: dict[str, Any]) -> float:
    """Deterministic preliminary **generation** quality score (0.0–1.0).

    This is NOT a semantic/AI quality score; it only reflects deterministic
    field completeness and validity (input/expected length, category,
    difficulty, duplicate penalty).
    """
    score = 0.0
    input_text = normalize_text(candidate.get("input"))
    expected = normalize_text(candidate.get("expected_output"))
    if len(input_text) >= 5:
        score += 0.3
    elif input_text:
        score += 0.15
    if len(expected) >= 5:
        score += 0.3
    elif expected:
        score += 0.15
    if candidate.get("category"):
        score += 0.2
    if candidate.get("difficulty") in DIFFICULTIES:
        score += 0.2
    if candidate.get("duplicate_of"):
        score -= 0.5
    return round(min(max(score, 0.0), 1.0), 4)
