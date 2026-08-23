"""Judge structured-response validation (Phase 4 §13–§14).

The judge model's JSON output is never trusted blindly. This module validates
the schema, required fields, score ranges, criterion names, confidence and
reasoning length. Any violation raises :class:`JudgeValidationError`, which the
evaluator maps to an ERROR result (EVALUATOR_ERROR) without crashing the run.
"""

from __future__ import annotations

import json
from typing import Any

from app.judge.base import JudgeError


class JudgeValidationError(JudgeError):
    """Raised when the judge model returns an invalid structured response."""


def _as_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise JudgeValidationError(f"Judge response field '{field}' must be numeric.") from exc


def validate_judge_response(
    raw: str,
    rubric: Any,
    max_reasoning_length: int = 2000,
) -> dict[str, Any]:
    """Parse and validate a judge model response against a rubric.

    Returns a normalized dict with ``criteria``, ``overall_score``, ``passed``,
    ``confidence`` and ``reasoning``.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise JudgeValidationError(f"Judge response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise JudgeValidationError("Judge response must be a JSON object.")

    required = ("criteria", "overall_score", "passed", "confidence", "reasoning")
    for field in required:
        if field not in data:
            raise JudgeValidationError(f"Judge response is missing '{field}'.")

    if not isinstance(data["criteria"], dict):
        raise JudgeValidationError("Judge response 'criteria' must be an object.")

    known = {c.name for c in rubric.criteria}
    bounds = {c.name: (c.min_score, c.max_score) for c in rubric.criteria}

    criteria: dict[str, float] = {}
    for name, value in data["criteria"].items():
        if name not in known:
            raise JudgeValidationError(f"Unknown criterion in judge response: {name}")
        score = _as_float(value, f"criteria.{name}")
        min_score, max_score = bounds[name]
        if not (min_score <= score <= max_score):
            raise JudgeValidationError(
                f"Criterion '{name}' score {score} is outside [{min_score}, {max_score}]."
            )
        criteria[name] = score

    overall = _as_float(data["overall_score"], "overall_score")
    if not (0.0 <= overall <= 1.0):
        raise JudgeValidationError(f"overall_score {overall} is outside [0, 1].")

    confidence = _as_float(data["confidence"], "confidence")
    if not (0.0 <= confidence <= 1.0):
        raise JudgeValidationError(f"confidence {confidence} is outside [0, 1].")

    if not isinstance(data["passed"], bool):
        raise JudgeValidationError("judge 'passed' must be a boolean.")

    reasoning = data["reasoning"]
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise JudgeValidationError("judge 'reasoning' must be a non-empty string.")
    if len(reasoning) > max_reasoning_length:
        raise JudgeValidationError("judge 'reasoning' exceeds the maximum length.")

    return {
        "criteria": criteria,
        "overall_score": overall,
        "passed": data["passed"],
        "confidence": confidence,
        "reasoning": reasoning,
    }
