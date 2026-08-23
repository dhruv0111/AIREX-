"""Rubric validation and deterministic weight normalization (Phase 4 §9, §23).

Validation rules:
- at least one criterion
- non-empty, unique criterion names
- non-empty criterion descriptions
- non-negative weights; total weight > 0
- valid score ranges (max_score > min_score)

Weights are normalized to sum to 1.0 deterministically.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import ValidationFailure


def validate_criteria(criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a list of criterion dicts and return normalized weights.

    Raises :class:`ValidationFailure` for any invalid input; never mutates the
    input list.
    """
    if not criteria:
        raise ValidationFailure("Rubric must contain at least one criterion.")

    seen: set[str] = set()
    total = 0.0
    for raw in criteria:
        name = str(raw.get("name") or "").strip()
        description = str(raw.get("description") or "").strip()
        if not name:
            raise ValidationFailure("Every criterion must have a non-empty name.")
        if name in seen:
            raise ValidationFailure(f"Duplicate criterion name: {name}")
        seen.add(name)
        if not description:
            raise ValidationFailure(f"Criterion '{name}' must have a non-empty description.")

        weight = raw.get("weight")
        if weight is None:
            raise ValidationFailure(f"Criterion '{name}' must specify a weight.")
        try:
            weight = float(weight)
        except (TypeError, ValueError) as exc:  # pragma: no cover - pydantic guards
            raise ValidationFailure(f"Criterion '{name}' weight must be numeric.") from exc
        if weight < 0:
            raise ValidationFailure(f"Criterion '{name}' weight must not be negative.")

        try:
            min_score = float(raw.get("min_score", 0.0))
            max_score = float(raw.get("max_score", 1.0))
        except (TypeError, ValueError) as exc:  # pragma: no cover - pydantic guards
            raise ValidationFailure(f"Criterion '{name}' score bounds must be numeric.") from exc
        if max_score <= min_score:
            raise ValidationFailure(f"Criterion '{name}' max_score must be greater than min_score.")
        total += weight

    if total <= 0:
        raise ValidationFailure("Total criterion weight must be greater than zero.")

    normalized: list[dict[str, Any]] = []
    for raw in criteria:
        item = dict(raw)
        item["weight"] = round(float(item["weight"]) / total, 6)
        normalized.append(item)
    return normalized
