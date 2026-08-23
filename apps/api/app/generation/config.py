"""Generation configuration validation (Phase 5 §"GENERATION CONFIGURATION")."""

from __future__ import annotations

from typing import Any

from app.core.errors import ValidationFailure

GENERATION_TYPES = ("BASIC", "EDGE_CASE", "BOUNDARY", "NEGATIVE", "AMBIGUOUS", "ADVERSARIAL")
SOURCE_TYPES = ("MANUAL_INSTRUCTION", "DATASET", "TEST_CASES", "EVALUATION_FAILURES")
DIFFICULTIES = ("easy", "medium", "hard")
DEFAULT_COUNT = 20
MAX_COUNT = 100


def validate_generation_type(value: Any) -> str:
    generation_type = str(value or "").upper()
    if generation_type not in GENERATION_TYPES:
        raise ValidationFailure(f"Invalid generation type: {value}")
    return generation_type


def validate_source_type(value: Any) -> str:
    source_type = str(value or "").upper()
    if source_type not in SOURCE_TYPES:
        raise ValidationFailure(f"Invalid source type: {value}")
    return source_type


def validate_generation_config(
    config: dict[str, Any] | None, count: int | None = None
) -> dict[str, Any]:
    """Validate and normalize a generation configuration.

    - ``count`` must be within [1, MAX_COUNT] (no unlimited generation).
    - ``generation_types`` must be a non-empty list of valid types.
    - ``difficulty_distribution`` weights must be non-negative with a positive
      total; weights are normalized to sum to 1.0 deterministically.
    """
    normalized = dict(config or {})

    requested = count if count is not None else normalized.get("count")
    requested = int(requested) if requested is not None else DEFAULT_COUNT
    if not (1 <= requested <= MAX_COUNT):
        raise ValidationFailure(f"count must be between 1 and {MAX_COUNT}.")
    normalized["count"] = requested

    types = normalized.get("generation_types")
    if types is None:
        types = [normalized.get("generation_type") or "BASIC"]
    if not isinstance(types, list) or not types:
        raise ValidationFailure("generation_types must be a non-empty list.")
    normalized["generation_types"] = [validate_generation_type(t) for t in types]

    distribution = normalized.get("difficulty_distribution")
    if distribution is not None:
        if not isinstance(distribution, dict):
            raise ValidationFailure("difficulty_distribution must be an object.")
        total = 0.0
        weights: dict[str, float] = {}
        for difficulty in DIFFICULTIES:
            try:
                weight = float(distribution.get(difficulty, 0.0))
            except (TypeError, ValueError) as exc:  # pragma: no cover - pydantic guards
                raise ValidationFailure(
                    f"difficulty_distribution['{difficulty}'] must be numeric."
                ) from exc
            if weight < 0:
                raise ValidationFailure(
                    f"difficulty_distribution['{difficulty}'] must not be negative."
                )
            weights[difficulty] = weight
            total += weight
        if total <= 0:
            raise ValidationFailure("difficulty_distribution must have a positive total weight.")
        normalized["difficulty_distribution"] = {
            difficulty: round(weight / total, 6) for difficulty, weight in weights.items()
        }
    return normalized
