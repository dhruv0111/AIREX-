"""Phase 5 unit tests: generation config validation, state machines, prompt
building, output parsing, fingerprinting, dedup and quality scoring (spec §
GENERATION CONFIGURATION, §SOURCE SNAPSHOT, §STRUCTURED OUTPUT, §DEDUP,
§QUALITY SCORE)."""

from __future__ import annotations

import pytest

from app.core.errors import ConflictError, ValidationFailure
from app.generation import (
    DEFAULT_COUNT,
    DIFFICULTIES,
    GENERATION_PROMPT_VERSION,
    GENERATION_TYPES,
    MAX_COUNT,
    SOURCE_TYPES,
    build_generation_messages,
    build_generation_prompt,
    compute_quality_score,
    fingerprint_candidate,
    parse_generation_output,
    render_source_material,
    validate_candidate_transition,
    validate_generation_config,
    validate_generation_type,
    validate_request_transition,
    validate_source_type,
)
from app.generation.parser import GenerationParseError

# ------------------------------------------------------------- config validation


def test_config_defaults_and_count():
    normalized = validate_generation_config(None)
    assert normalized["count"] == DEFAULT_COUNT
    assert normalized["generation_types"] == ["BASIC"]


def test_config_count_bounds():
    with pytest.raises(ValidationFailure):
        validate_generation_config(None, count=0)
    with pytest.raises(ValidationFailure):
        validate_generation_config(None, count=MAX_COUNT + 1)


def test_config_generation_types_upper():
    normalized = validate_generation_config({"generation_types": ["edge_case"]})
    assert normalized["generation_types"] == ["EDGE_CASE"]


def test_config_rejects_empty_types():
    with pytest.raises(ValidationFailure):
        validate_generation_config({"generation_types": []})


def test_config_rejects_unknown_type():
    with pytest.raises(ValidationFailure):
        validate_generation_config({"generation_types": ["MAGIC"]})


def test_config_normalizes_difficulty_distribution():
    normalized = validate_generation_config(
        {"difficulty_distribution": {"easy": 1, "medium": 1, "hard": 2}}
    )
    dist = normalized["difficulty_distribution"]
    assert dist["hard"] == pytest.approx(0.5, abs=0.001)
    assert dist["easy"] == pytest.approx(0.25, abs=0.001)
    assert sum(dist.values()) == pytest.approx(1.0, abs=0.001)


def test_config_rejects_negative_difficulty_weight():
    with pytest.raises(ValidationFailure):
        validate_generation_config({"difficulty_distribution": {"easy": -1}})


def test_config_rejects_zero_total_weight():
    with pytest.raises(ValidationFailure):
        validate_generation_config({"difficulty_distribution": {"easy": 0}})


def test_config_rejects_non_dict_distribution():
    with pytest.raises(ValidationFailure):
        validate_generation_config({"difficulty_distribution": [1, 2]})


# ---------------------------------------------------------------- type helpers


def test_validate_generation_type():
    assert validate_generation_type("boundary") == "BOUNDARY"
    with pytest.raises(ValidationFailure):
        validate_generation_type("nonsense")


def test_validate_source_type():
    assert validate_source_type("dataset") == "DATASET"
    with pytest.raises(ValidationFailure):
        validate_source_type("nonsense")


def test_constants_shape():
    assert "ADVERSARIAL" in GENERATION_TYPES
    assert "EVALUATION_FAILURES" in SOURCE_TYPES
    assert set(DIFFICULTIES) == {"easy", "medium", "hard"}


# --------------------------------------------------------------- state machines


def test_request_transitions():
    validate_request_transition("QUEUED", "RUNNING")
    validate_request_transition("RUNNING", "COMPLETED")
    with pytest.raises(ConflictError):
        validate_request_transition("COMPLETED", "RUNNING")
    with pytest.raises(ConflictError):
        validate_request_transition("FAILED", "COMPLETED")


def test_candidate_transitions():
    validate_candidate_transition("PENDING_REVIEW", "APPROVED")
    validate_candidate_transition("PENDING_REVIEW", "REJECTED")
    with pytest.raises(ConflictError):
        validate_candidate_transition("APPROVED", "REJECTED")
    with pytest.raises(ConflictError):
        validate_candidate_transition("REJECTED", "APPROVED")


# ------------------------------------------------------------------ prompt build


def test_prompt_version_pinned():
    assert GENERATION_PROMPT_VERSION == "1.0.0"


def test_build_generation_prompt_contains_fields():
    prompt = build_generation_prompt(
        instruction="Summarize the text",
        generation_type="EDGE_CASE",
        difficulty_distribution={"easy": 0.5, "hard": 0.5},
        source_material='{"input": "x"}',
        count=10,
    )
    assert "Summarize the text" in prompt
    assert "EDGE_CASE" in prompt
    assert "10" in prompt
    assert "test_cases" in prompt


def test_build_generation_messages_shape():
    messages = build_generation_messages(
        instruction=None,
        generation_type="BASIC",
        difficulty_distribution=None,
        source_material=None,
        count=5,
    )
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "(none)" in messages[1]["content"]


def test_render_source_material_truncates():
    source = [{"input": "a" * 20000}]
    rendered = render_source_material(source)
    assert len(rendered) <= 12000
    assert render_source_material([]) == "(none)"


# ------------------------------------------------------------------ output parse


def _valid_candidate(overrides=None):
    item = {
        "input": "What is 2+2?",
        "expected_output": "4",
        "context": {"topic": "math"},
        "category": "arithmetic",
        "difficulty": "easy",
        "generation_type": "BASIC",
    }
    if overrides:
        item.update(overrides)
    return item


def test_parse_generation_output_valid():
    payload = {"test_cases": [_valid_candidate(), _valid_candidate({"input": "Q2"})]}
    raw = __import__("json").dumps(payload)
    valid, rejected = parse_generation_output(raw, "BASIC")
    assert rejected == 0
    assert len(valid) == 2
    assert valid[0]["input"] == "What is 2+2?"
    assert valid[0]["generation_type"] == "BASIC"


def test_parse_generation_output_malformed_raises():
    with pytest.raises(GenerationParseError):
        parse_generation_output("not json", "BASIC")
    with pytest.raises(GenerationParseError):
        parse_generation_output('{"foo": 1}', "BASIC")


def test_parse_generation_output_skips_invalid_rows():
    bad = _valid_candidate({"input": ""})
    payload = {"test_cases": [_valid_candidate(), bad, _valid_candidate({"difficulty": "nope"})]}
    raw = __import__("json").dumps(payload)
    valid, rejected = parse_generation_output(raw, "BASIC")
    assert rejected == 2
    assert len(valid) == 1


def test_parse_generation_output_defaults_type_and_difficulty():
    item = {"input": "x", "expected_output": "y"}
    payload = {"test_cases": [item]}
    raw = __import__("json").dumps(payload)
    valid, _ = parse_generation_output(raw, "NEGATIVE")
    assert valid[0]["generation_type"] == "NEGATIVE"
    assert valid[0]["difficulty"] == "medium"


def test_validate_candidate_rejects_oversized_input():
    from app.generation.parser import validate_candidate

    with pytest.raises(GenerationParseError):
        validate_candidate(_valid_candidate({"input": "a" * 8001}), "BASIC")
    with pytest.raises(GenerationParseError):
        validate_candidate(_valid_candidate({"expected_output": "b" * 8001}), "BASIC")


def test_validate_candidate_rejects_bad_category_length():
    from app.generation.parser import validate_candidate

    with pytest.raises(GenerationParseError):
        validate_candidate(_valid_candidate({"category": "c" * 101}), "BASIC")


def test_validate_candidate_rejects_empty_expected_output():
    from app.generation.parser import validate_candidate

    with pytest.raises(GenerationParseError):
        validate_candidate(_valid_candidate({"expected_output": ""}), "BASIC")


def test_validate_candidate_rejects_invalid_generation_type():
    from app.generation.parser import validate_candidate

    with pytest.raises(GenerationParseError):
        validate_candidate(_valid_candidate({"generation_type": "MAGIC"}), "BASIC")


def test_validate_candidate_strips_non_dict_context():
    from app.generation.parser import validate_candidate

    validated = validate_candidate(_valid_candidate({"context": "not a dict"}), "BASIC")
    assert validated["context"] is None


def test_parse_generation_output_skips_non_dict_items():
    payload = {"test_cases": [_valid_candidate(), "not-a-dict", 42, None]}
    raw = __import__("json").dumps(payload)
    valid, rejected = parse_generation_output(raw, "BASIC")
    assert rejected == 3
    assert len(valid) == 1


# ----------------------------------------------------------- fingerprint + dedup


def test_fingerprint_deterministic():
    a = fingerprint_candidate(input_text="  hello   world ", expected_output="hi", context=None)
    b = fingerprint_candidate(input_text="hello world", expected_output="hi", context=None)
    assert a == b
    assert len(a) == 64


def test_fingerprint_differs_by_content():
    a = fingerprint_candidate(input_text="q1", expected_output="a1", context=None)
    b = fingerprint_candidate(input_text="q1", expected_output="a2", context=None)
    assert a != b


def test_fingerprint_includes_context():
    a = fingerprint_candidate(input_text="q", expected_output="a", context={"k": 1})
    b = fingerprint_candidate(input_text="q", expected_output="a", context={"k": 2})
    assert a != b


# --------------------------------------------------------------- quality score


def test_quality_score_deterministic_full():
    score = compute_quality_score(
        {
            "input": "a" * 20,
            "expected_output": "b" * 20,
            "category": "c",
            "difficulty": "hard",
        }
    )
    assert score == pytest.approx(1.0, abs=0.001)


def test_quality_score_minimal():
    score = compute_quality_score(
        {"input": "a", "expected_output": "b", "category": None, "difficulty": None}
    )
    assert score < 1.0
    assert 0.0 <= score <= 1.0


def test_quality_score_duplicate_penalty():
    base = {"input": "a" * 20, "expected_output": "b" * 20, "category": "c", "difficulty": "easy"}
    assert compute_quality_score(base) == 1.0
    penalized = compute_quality_score({**base, "duplicate_of": "some-id"})
    assert penalized == pytest.approx(0.5, abs=0.001)


# ------------------------------------------------------------- metrics helpers


def test_metrics_helpers():
    from app.core.metrics import metrics_enabled, metrics_response, report_db_status

    report_db_status(True)
    report_db_status(False)
    response = metrics_response()
    assert response.status_code == 200
    assert b"http_requests_total" in response.body
    assert isinstance(metrics_enabled(), bool)
