"""Phase 4 unit tests: rubric validation, judge response validation, prompt
building, judge caching, pass-policy scoring, judge snapshots (spec §9, §13–§14,
§15–§16, §34–§35, §41)."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationFailure
from app.evaluations.aggregate import apply_pass_policy
from app.judge.base import JudgeCriterion, JudgeRubric
from app.judge.cache import JudgeCache
from app.judge.prompts import JUDGE_PROMPT_VERSION, build_judge_prompt
from app.judge.validation import JudgeValidationError, validate_judge_response
from app.rubrics.validation import validate_criteria

# ------------------------------------------------------------- rubric validation


def test_validate_criteria_normalizes_weights():
    normalized = validate_criteria(
        [
            {"name": "correctness", "description": "Correct", "weight": 50},
            {"name": "relevance", "description": "Relevant", "weight": 30},
            {"name": "clarity", "description": "Clear", "weight": 20},
        ]
    )
    assert sum(c["weight"] for c in normalized) == pytest.approx(1.0, abs=0.01)
    assert normalized[0]["weight"] == pytest.approx(0.5, abs=0.01)


def test_validate_criteria_rejects_empty():
    with pytest.raises(ValidationFailure):
        validate_criteria([])


def test_validate_criteria_rejects_missing_name():
    with pytest.raises(ValidationFailure):
        validate_criteria([{"name": "", "description": "x", "weight": 1.0}])


def test_validate_criteria_rejects_duplicate_name():
    with pytest.raises(ValidationFailure):
        validate_criteria(
            [
                {"name": "a", "description": "x", "weight": 0.5},
                {"name": "a", "description": "y", "weight": 0.5},
            ]
        )


def test_validate_criteria_rejects_missing_description():
    with pytest.raises(ValidationFailure):
        validate_criteria([{"name": "a", "description": "", "weight": 1.0}])


def test_validate_criteria_rejects_negative_weight():
    with pytest.raises(ValidationFailure):
        validate_criteria([{"name": "a", "description": "x", "weight": -0.1}])


def test_validate_criteria_rejects_zero_total():
    with pytest.raises(ValidationFailure):
        validate_criteria(
            [
                {"name": "a", "description": "x", "weight": 0},
                {"name": "b", "description": "y", "weight": 0},
            ]
        )


def test_validate_criteria_rejects_invalid_score_range():
    with pytest.raises(ValidationFailure):
        validate_criteria(
            [{"name": "a", "description": "x", "weight": 1.0, "min_score": 0.5, "max_score": 0.5}]
        )


# ------------------------------------------------------------- judge validation


def _rubric() -> JudgeRubric:
    return JudgeRubric(
        name="Answer Quality",
        description=None,
        version=1,
        criteria=[
            JudgeCriterion("correctness", "Factually correct", 0.5),
            JudgeCriterion("relevance", "Directly addresses the question", 0.3),
            JudgeCriterion("clarity", "Understandable", 0.2),
        ],
    )


_VALID = (
    '{"criteria": {"correctness": 0.9, "relevance": 0.8, "clarity": 1.0}, '
    '"overall_score": 0.89, "passed": true, "confidence": 0.91, '
    '"reasoning": "Factually correct and directly relevant."}'
)


def test_judge_validation_valid():
    result = validate_judge_response(_VALID, _rubric())
    assert result["overall_score"] == 0.89
    assert result["criteria"]["correctness"] == 0.9
    assert result["passed"] is True
    assert result["confidence"] == 0.91


def test_judge_validation_malformed_json():
    with pytest.raises(JudgeValidationError):
        validate_judge_response("not json", _rubric())


def test_judge_validation_plain_text_rejected():
    with pytest.raises(JudgeValidationError):
        validate_judge_response("The answer is good.", _rubric())


def test_judge_validation_missing_fields():
    with pytest.raises(JudgeValidationError):
        validate_judge_response('{"overall_score": 0.5}', _rubric())


def test_judge_validation_score_out_of_range():
    raw = (
        '{"criteria": {"correctness": 1.5}, "overall_score": 0.5, "passed": true, '
        '"confidence": 0.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_overall_out_of_range():
    raw = (
        '{"criteria": {}, "overall_score": 1.2, "passed": true, '
        '"confidence": 0.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_unknown_criterion():
    raw = (
        '{"criteria": {"wrong_name": 0.5}, "overall_score": 0.5, "passed": true, '
        '"confidence": 0.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_confidence_out_of_range():
    raw = (
        '{"criteria": {}, "overall_score": 0.5, "passed": true, '
        '"confidence": 1.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_passed_must_be_bool():
    raw = (
        '{"criteria": {}, "overall_score": 0.5, "passed": "yes", '
        '"confidence": 0.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_empty_reasoning():
    raw = (
        '{"criteria": {}, "overall_score": 0.5, "passed": true, "confidence": 0.5, "reasoning": ""}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_overlong_reasoning():
    raw = (
        '{"criteria": {}, "overall_score": 0.5, "passed": true, "confidence": 0.5, '
        f'"reasoning": "{"x" * 3000}"}}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_criterion_non_numeric():
    raw = (
        '{"criteria": {"correctness": "high"}, "overall_score": 0.5, "passed": true, '
        '"confidence": 0.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_overall_non_numeric():
    raw = (
        '{"criteria": {}, "overall_score": "high", "passed": true, '
        '"confidence": 0.5, "reasoning": "x"}'
    )
    with pytest.raises(JudgeValidationError):
        validate_judge_response(raw, _rubric())


def test_judge_validation_non_object_response():
    with pytest.raises(JudgeValidationError):
        validate_judge_response("[1, 2, 3]", _rubric())


def test_base_evaluator_default_sync_raises():
    from app.evaluators.base import BaseEvaluator, EvaluatorError

    evaluator = BaseEvaluator()
    with pytest.raises(EvaluatorError):
        evaluator.evaluate(expected="a", actual="b", config={})


@pytest.mark.asyncio
async def test_base_evaluator_default_async_raises():
    from app.evaluators.base import BaseEvaluator, EvaluatorError

    evaluator = BaseEvaluator()
    with pytest.raises(EvaluatorError):
        await evaluator.evaluate_async(
            input_text="a", expected_output=None, actual_output="b", context=None, config={}
        )


# ------------------------------------------------------------------- prompt


def test_prompt_includes_input_expected_actual_rubric():
    prompt = build_judge_prompt(
        input_text="Explain photosynthesis?",
        expected_output="Plants convert light to energy",
        actual_output="Plants use sunlight",
        rubric=_rubric(),
    )
    assert "Explain photosynthesis?" in prompt
    assert "Plants convert light to energy" in prompt
    assert "Plants use sunlight" in prompt
    assert "correctness" in prompt
    assert JUDGE_PROMPT_VERSION == "1.0.0"


def test_prompt_reference_free_omits_expected():
    prompt = build_judge_prompt(
        input_text="How are you?",
        expected_output="SECRET-EXPECTED",
        actual_output="Fine",
        rubric=_rubric(),
        include_reference=False,
    )
    assert "SECRET-EXPECTED" not in prompt


def test_prompt_context_when_absent_is_none():
    prompt = build_judge_prompt(
        input_text="q", expected_output=None, actual_output="a", rubric=_rubric(), context=None
    )
    assert "(none)" in prompt


def test_prompt_contains_no_secrets():
    # AT-P4-040: judge prompts must never carry credentials/keys.
    prompt = build_judge_prompt(
        input_text="q", expected_output="e", actual_output="a", rubric=_rubric(), context="c"
    )
    for secret in ("sk-", "api_key", "authorization", "Bearer ", "secret"):
        assert secret not in prompt


# ------------------------------------------------------------------- cache


def test_cache_key_changes_with_content():
    base = dict(
        target_output="out",
        input_text="in",
        expected_output="exp",
        context=None,
        rubric_version=1,
        judge_model="judge-1",
        judge_prompt_version="1.0.0",
    )
    k1 = JudgeCache.make_key(**base)
    k2 = JudgeCache.make_key(**{**base, "rubric_version": 2})
    k3 = JudgeCache.make_key(**{**base, "judge_model": "judge-2"})
    k4 = JudgeCache.make_key(**{**base, "target_output": "different"})
    assert k1 != k2
    assert k1 != k3
    assert k1 != k4


@pytest.mark.asyncio
async def test_cache_is_organization_scoped():
    cache = JudgeCache()
    key = JudgeCache.make_key(
        target_output="out",
        input_text="in",
        expected_output=None,
        context=None,
        rubric_version=1,
        judge_model="m",
        judge_prompt_version="1.0.0",
    )
    org_a = "11111111-1111-1111-1111-111111111111"
    org_b = "22222222-2222-2222-2222-222222222222"
    import uuid

    await cache.put(uuid.UUID(org_a), key, {"score": 0.9})
    assert await cache.get(uuid.UUID(org_a), key) == {"score": 0.9}
    assert await cache.get(uuid.UUID(org_b), key) is None  # no leakage


# -------------------------------------------------------------- pass policy


def _score(score: float, passed: bool) -> dict:
    return {"evaluator": "e", "version": "1.0.0", "score": score, "passed": passed, "reason": "r"}


def test_pass_policy_any():
    passed, combined = apply_pass_policy([_score(0.0, False), _score(1.0, True)], pass_policy="ANY")
    assert passed is True
    assert combined is None


def test_pass_policy_all_fail():
    passed, combined = apply_pass_policy([_score(0.0, False), _score(1.0, True)], pass_policy="ALL")
    assert passed is False


def test_pass_policy_weighted_exact_math():
    scores = [_score(0.9, True), _score(0.8, True), _score(1.0, True)]
    passed, combined = apply_pass_policy(
        scores, pass_policy="WEIGHTED", threshold=0.75, weights=[0.5, 0.3, 0.2]
    )
    assert combined == pytest.approx(0.89)
    assert passed is True


def test_pass_policy_weighted_threshold_fail():
    scores = [_score(0.6, True), _score(0.5, True)]
    passed, combined = apply_pass_policy(
        scores, pass_policy="WEIGHTED", threshold=0.75, weights=[1.0, 1.0]
    )
    assert combined == pytest.approx(0.55)
    assert passed is False


# ----------------------------------------------------------- judge snapshots


def test_judge_rubric_from_snapshot():
    rubric = JudgeRubric.from_snapshot(
        {
            "name": "Answer Quality",
            "version": 2,
            "criteria": [
                {
                    "name": "correctness",
                    "description": "Correct",
                    "weight": 0.5,
                    "min_score": 0.0,
                    "max_score": 1.0,
                }
            ],
        }
    )
    assert rubric.name == "Answer Quality"
    assert rubric.version == 2
    assert rubric.criteria[0].weight == 0.5
