"""Deterministic core evaluators (Phase 3 §14–§21).

No LLM-as-a-judge: all evaluators here are deterministic, provider-independent
and reproducible. Invalid execution (e.g. an invalid regex) raises
:class:`EvaluatorError` so the run records an ERROR result instead of crashing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluationScore, EvaluatorError

_VERSION = "1.0.0"


def _text(value: str | None) -> str:
    return (value or "").strip()


class ExactMatchEvaluator(BaseEvaluator):
    name = "exact_match"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        if expected is None:
            return self._fail("No expected output provided for exact match.")
        if _text(expected) == _text(actual):
            return self._pass("Output exactly matched expected output.")
        return self._fail("Output did not match expected output.")


class CaseInsensitiveExactMatchEvaluator(BaseEvaluator):
    name = "case_insensitive_exact_match"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        if expected is None:
            return self._fail("No expected output provided for case-insensitive match.")
        if _text(expected).lower() == _text(actual).lower():
            return self._pass("Output matched expected output ignoring case.")
        return self._fail("Output did not match expected output (case-insensitive).")


class ContainsEvaluator(BaseEvaluator):
    name = "contains"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        if expected is None:
            return self._fail("No expected substring provided for contains.")
        if expected in (actual or ""):
            return self._pass("Expected substring found in output.")
        return self._fail("Expected substring not found in output.")


class RegexEvaluator(BaseEvaluator):
    name = "regex"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        if expected is None:
            raise EvaluatorError("Regex evaluator requires an expected pattern.")
        try:
            pattern = re.compile(expected)
        except re.error as exc:
            raise EvaluatorError(f"Invalid regex: {exc}")
        if pattern.search(actual or ""):
            return self._pass("Output matched the expected regex.")
        return self._fail("Output did not match the expected regex.")


class JsonMatchEvaluator(BaseEvaluator):
    name = "json_match"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        if expected is None:
            raise EvaluatorError("JSON evaluator requires an expected JSON value.")
        try:
            expected_value = json.loads(expected)
        except json.JSONDecodeError as exc:
            raise EvaluatorError(f"Expected output is not valid JSON: {exc.msg}")
        try:
            actual_value = json.loads(actual or "")
        except json.JSONDecodeError as exc:
            return self._fail(f"Actual output is not valid JSON: {exc.msg}")
        if expected_value == actual_value:
            return self._pass("JSON structures matched (key order independent).")
        return self._fail("JSON structures did not match.")


class NumericMatchEvaluator(BaseEvaluator):
    name = "numeric_match"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        if expected is None:
            raise EvaluatorError("Numeric evaluator requires an expected numeric value.")
        tolerance = float(config.get("tolerance", 0.0))
        try:
            expected_value = float(expected)
        except ValueError as exc:
            raise EvaluatorError(f"Expected output is not numeric: {exc}")
        try:
            actual_value = float(actual or "")
        except ValueError as exc:
            return self._fail(f"Actual output is not numeric: {exc}")
        if abs(actual_value - expected_value) <= tolerance:
            return self._pass(
                "Numeric output matched within tolerance.",
                metadata={
                    "expected": expected_value,
                    "actual": actual_value,
                    "tolerance": tolerance,
                },
            )
        return self._fail(
            "Numeric output outside tolerance.",
            metadata={"expected": expected_value, "actual": actual_value, "tolerance": tolerance},
        )


class LengthEvaluator(BaseEvaluator):
    name = "length"
    version = _VERSION

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        min_length = config.get("min_length")
        max_length = config.get("max_length")
        if min_length is None and max_length is None:
            raise EvaluatorError("Length evaluator requires min_length and/or max_length.")
        length = len(actual or "")
        if min_length is not None and length < int(min_length):
            return self._fail(f"Output length {length} is below min_length {min_length}.")
        if max_length is not None and length > int(max_length):
            return self._fail(f"Output length {length} exceeds max_length {max_length}.")
        return self._pass(
            "Output length satisfied constraints.",
            metadata={"length": length, "min_length": min_length, "max_length": max_length},
        )
