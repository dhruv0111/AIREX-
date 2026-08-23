"""Unit tests for the deterministic evaluators, registry, aggregation and the
evaluation state machine (Phase 3 §22, §31–§32, §42, §63)."""

from __future__ import annotations

import pytest

from app.core.errors import ConflictError
from app.evaluations.aggregate import compute_evaluator_metrics, compute_run_metrics
from app.evaluations.state import validate_transition
from app.evaluators import EvaluatorError, default_registry

REGISTRY = default_registry()


def _build(name: str):
    return REGISTRY.build(name)


# ------------------------------------------------------------------ registry


def test_registry_has_all_core_evaluators():
    assert REGISTRY.names() == [
        "case_insensitive_exact_match",
        "contains",
        "exact_match",
        "json_match",
        "length",
        "llm_judge",
        "numeric_match",
        "regex",
    ]
    assert REGISTRY.versions()["exact_match"] == "1.0.0"


def test_registry_unknown_evaluator_raises():
    with pytest.raises(EvaluatorError):
        _build("nope")


# ------------------------------------------------------------------ exact


def test_exact_match_pass():
    score = _build("exact_match").evaluate(expected="New Delhi", actual="New Delhi", config={})
    assert score.passed and score.score == 1.0


def test_exact_match_fail():
    score = _build("exact_match").evaluate(expected="New Delhi", actual="Mumbai", config={})
    assert not score.passed and score.score == 0.0


def test_exact_match_missing_expected_is_fail():
    score = _build("exact_match").evaluate(expected=None, actual="x", config={})
    assert not score.passed


# ------------------------------------------------------------------ case-insensitive


def test_case_insensitive_exact_match_pass():
    score = _build("case_insensitive_exact_match").evaluate(
        expected="New Delhi", actual="  new delhi  ", config={}
    )
    assert score.passed


def test_case_insensitive_exact_match_missing_expected_is_fail():
    score = _build("case_insensitive_exact_match").evaluate(expected=None, actual="x", config={})
    assert not score.passed


def test_case_insensitive_exact_match_mismatch_is_fail():
    score = _build("case_insensitive_exact_match").evaluate(
        expected="New Delhi", actual="Mumbai", config={}
    )
    assert not score.passed


# ------------------------------------------------------------------ contains


def test_contains_pass():
    score = _build("contains").evaluate(
        expected="New Delhi", actual="The capital of India is New Delhi.", config={}
    )
    assert score.passed


def test_contains_fail():
    score = _build("contains").evaluate(expected="Tokyo", actual="New Delhi", config={})
    assert not score.passed


def test_contains_missing_expected_is_fail():
    score = _build("contains").evaluate(expected=None, actual="x", config={})
    assert not score.passed


# ------------------------------------------------------------------ regex


def test_regex_pass():
    score = _build("regex").evaluate(expected=r"^Order-[0-9]+$", actual="Order-12345", config={})
    assert score.passed


def test_regex_invalid_raises_evaluator_error():
    with pytest.raises(EvaluatorError):
        _build("regex").evaluate(expected="([", actual="x", config={})


def test_regex_missing_expected_raises():
    with pytest.raises(EvaluatorError):
        _build("regex").evaluate(expected=None, actual="x", config={})


def test_regex_no_match_is_fail():
    score = _build("regex").evaluate(expected=r"^A", actual="B", config={})
    assert not score.passed


# ------------------------------------------------------------------ json


def test_json_match_key_order_independent():
    score = _build("json_match").evaluate(
        expected='{"status":"success","count":10}',
        actual='{"count":10,"status":"success"}',
        config={},
    )
    assert score.passed


def test_json_match_actual_invalid_is_fail():
    score = _build("json_match").evaluate(expected='{"a":1}', actual="not json", config={})
    assert not score.passed


def test_json_match_missing_expected_raises():
    with pytest.raises(EvaluatorError):
        _build("json_match").evaluate(expected=None, actual='{"a":1}', config={})


def test_json_match_invalid_expected_raises():
    with pytest.raises(EvaluatorError):
        _build("json_match").evaluate(expected="not json", actual='{"a":1}', config={})


def test_json_match_mismatch_is_fail():
    score = _build("json_match").evaluate(expected='{"a":1}', actual='{"a":2}', config={})
    assert not score.passed


# ------------------------------------------------------------------ numeric


def test_numeric_match_within_tolerance():
    score = _build("numeric_match").evaluate(
        expected="100", actual="100.02", config={"tolerance": 0.05}
    )
    assert score.passed


def test_numeric_match_outside_tolerance():
    score = _build("numeric_match").evaluate(
        expected="100", actual="100.5", config={"tolerance": 0.01}
    )
    assert not score.passed


def test_numeric_match_actual_not_numeric_is_fail():
    score = _build("numeric_match").evaluate(expected="100", actual="abc", config={})
    assert not score.passed


def test_numeric_match_missing_expected_raises():
    with pytest.raises(EvaluatorError):
        _build("numeric_match").evaluate(expected=None, actual="1", config={})


def test_numeric_match_invalid_expected_raises():
    with pytest.raises(EvaluatorError):
        _build("numeric_match").evaluate(expected="abc", actual="1", config={})


# ------------------------------------------------------------------ length


def test_length_within_bounds():
    score = _build("length").evaluate(
        expected=None, actual="hello world!!", config={"min_length": 10, "max_length": 200}
    )
    assert score.passed


def test_length_below_min_fails():
    score = _build("length").evaluate(expected=None, actual="short", config={"min_length": 100})
    assert not score.passed


def test_length_requires_config():
    with pytest.raises(EvaluatorError):
        _build("length").evaluate(expected=None, actual="x", config={})


def test_length_exceeds_max_fails():
    score = _build("length").evaluate(expected=None, actual="toolong", config={"max_length": 3})
    assert not score.passed


# ------------------------------------------------------------- aggregation


def test_compute_run_metrics():
    rows = [
        SimpleResult("PASS", 100, 10, 5, 15),
        SimpleResult("PASS", 200, 20, 10, 30),
        SimpleResult("FAIL", 300, 5, 5, 10),
        SimpleResult("ERROR", None, 0, 0, 0),
    ]
    metrics = compute_run_metrics(rows)
    assert metrics["total_tests"] == 4
    assert metrics["passed"] == 2
    assert metrics["failed"] == 1
    assert metrics["errors"] == 1
    assert metrics["pass_rate"] == 0.5
    assert metrics["fail_rate"] == 0.25
    assert metrics["error_rate"] == 0.25
    assert metrics["p50_latency_ms"] == 200
    # p95 uses linear interpolation: index=(3-1)*0.95=1.9 -> 200+(300-200)*0.9=290.0
    assert metrics["p95_latency_ms"] == 290.0
    assert metrics["total_tokens"] == 55


def test_compute_evaluator_metrics():
    rows = [
        SimpleResult(
            "PASS",
            None,
            0,
            0,
            0,
            score=[
                {"evaluator": "exact_match", "version": "1.0.0", "score": 1.0, "passed": True},
            ],
        ),
        SimpleResult(
            "FAIL",
            None,
            0,
            0,
            0,
            score=[
                {"evaluator": "exact_match", "version": "1.0.0", "score": 0.0, "passed": False},
            ],
        ),
    ]
    metrics = compute_evaluator_metrics(rows)
    assert metrics["exact_match"]["count"] == 2
    assert metrics["exact_match"]["passed"] == 1
    assert metrics["exact_match"]["failed"] == 1
    assert metrics["exact_match"]["pass_rate"] == 0.5
    assert metrics["exact_match"]["average_score"] == 0.5


# ------------------------------------------------------------- state machine


def test_valid_transitions():
    validate_transition("QUEUED", "RUNNING")
    validate_transition("RUNNING", "COMPLETED")
    validate_transition("RUNNING", "FAILED")
    validate_transition("QUEUED", "CANCELLED")
    validate_transition("RUNNING", "CANCELLED")


def test_invalid_transitions_rejected():
    with pytest.raises(ConflictError):
        validate_transition("COMPLETED", "RUNNING")
    with pytest.raises(ConflictError):
        validate_transition("CANCELLED", "RUNNING")
    with pytest.raises(ConflictError):
        validate_transition("RUNNING", "QUEUED")


class SimpleResult:
    """Minimal stand-in for an EvaluationResult row."""

    def __init__(self, status, latency_ms, input_tokens, output_tokens, total_tokens, score=None):
        self.status = status
        self.latency_ms = latency_ms
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.score = score
