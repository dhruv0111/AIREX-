"""Structured generation output parser + candidate schema validation (Phase 5).

A malformed top-level JSON payload raises :class:`GenerationParseError` (the
generation FAILS); an individual invalid candidate is skipped (rejected from
persistence) so one bad row never discards the whole batch.
"""

from __future__ import annotations

import json
from typing import Any

from app.generation.config import DIFFICULTIES, GENERATION_TYPES


class GenerationParseError(Exception):
    """Raised when the generator output cannot be parsed / used."""


_MAX_FIELD_LENGTH = 8000
_MAX_CATEGORY_LENGTH = 100


def validate_candidate(item: dict[str, Any], expected_type: str) -> dict[str, Any]:
    """Validate a single candidate dict; raises GenerationParseError if invalid."""
    input_text = str(item.get("input") or "").strip()
    if not input_text:
        raise GenerationParseError("Candidate 'input' must be non-empty.")
    if len(input_text) > _MAX_FIELD_LENGTH:
        raise GenerationParseError("Candidate 'input' exceeds the maximum length.")

    expected = item.get("expected_output")
    expected_text = str(expected).strip() if expected is not None else ""
    if not expected_text:
        raise GenerationParseError("Candidate 'expected_output' must be non-empty.")
    if len(expected_text) > _MAX_FIELD_LENGTH:
        raise GenerationParseError("Candidate 'expected_output' exceeds the maximum length.")

    generation_type = str(item.get("generation_type") or expected_type).upper()
    if generation_type not in GENERATION_TYPES:
        raise GenerationParseError(f"Invalid generation_type: {generation_type}")

    difficulty = str(item.get("difficulty") or "medium").lower()
    if difficulty not in DIFFICULTIES:
        raise GenerationParseError(f"Invalid difficulty: {difficulty}")

    category = str(item.get("category") or "").strip()
    if len(category) > _MAX_CATEGORY_LENGTH:
        raise GenerationParseError("Candidate 'category' exceeds the maximum length.")

    context = item.get("context")
    return {
        "input": input_text,
        "expected_output": expected_text,
        "context": context if isinstance(context, dict) and context else None,
        "category": category or None,
        "generation_type": generation_type,
        "difficulty": difficulty,
    }


def parse_generation_output(raw: str, expected_type: str) -> tuple[list[dict[str, Any]], int]:
    """Parse generator JSON into valid candidates.

    Returns ``(valid_candidates, rejected_count)``. Raises
    :class:`GenerationParseError` when the top-level payload is malformed.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GenerationParseError(f"Generator output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("test_cases"), list):
        raise GenerationParseError("Generator output must be an object with a 'test_cases' list.")

    valid: list[dict[str, Any]] = []
    rejected = 0
    for item in data["test_cases"]:
        if not isinstance(item, dict):
            rejected += 1
            continue
        try:
            valid.append(validate_candidate(item, expected_type))
        except GenerationParseError:
            rejected += 1
    return valid, rejected
