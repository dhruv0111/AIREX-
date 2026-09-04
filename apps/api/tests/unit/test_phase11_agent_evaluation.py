"""Unit tests for Phase 11 AI Agent Evaluation & Trajectory Testing."""

import pytest
from app.services.agent_gateway import compute_agent_fingerprint
from app.services.agent_reliability import AgentReliabilityScorer
from app.services.loop_detector import LoopDetector
from app.services.tool_evaluator import ToolEvaluator, redact_sensitive_data
from app.services.trajectory_evaluator import TrajectoryEvaluator


def test_loop_detector_repeated_identical_tool():
    """Identical tool + identical args repeated >= 3 times triggers REPEATED_IDENTICAL_TOOL loop."""
    detector = LoopDetector()
    steps = [
        {"step_number": 1, "step_type": "MODEL_REQUEST"},
        {"step_number": 2, "step_type": "TOOL_CALL", "tool_name": "search", "tool_arguments": {"query": "weather"}},
        {"step_number": 3, "step_type": "TOOL_RESULT", "tool_name": "search"},
        {"step_number": 4, "step_type": "TOOL_CALL", "tool_name": "search", "tool_arguments": {"query": "weather"}},
        {"step_number": 5, "step_type": "TOOL_RESULT", "tool_name": "search"},
        {"step_number": 6, "step_type": "TOOL_CALL", "tool_name": "search", "tool_arguments": {"query": "weather"}},
        {"step_number": 7, "step_type": "TOOL_RESULT", "tool_name": "search"},
    ]
    res = detector.detect(steps)
    assert res["is_loop_detected"] is True
    assert res["loop_type"] == "REPEATED_IDENTICAL_TOOL"
    assert res["loop_count"] >= 3
    assert len(res["step_references"]) >= 3


def test_loop_detector_cyclic_sequence():
    """Cyclic tool sequences like A -> B -> A -> B -> A -> B trigger CYCLIC_TOOL_SEQUENCE loop."""
    detector = LoopDetector()
    steps = [
        {"step_number": 1, "step_type": "TOOL_CALL", "tool_name": "tool_a", "tool_arguments": {"a": 1}},
        {"step_number": 2, "step_type": "TOOL_CALL", "tool_name": "tool_b", "tool_arguments": {"b": 1}},
        {"step_number": 3, "step_type": "TOOL_CALL", "tool_name": "tool_a", "tool_arguments": {"a": 2}},
        {"step_number": 4, "step_type": "TOOL_CALL", "tool_name": "tool_b", "tool_arguments": {"b": 2}},
        {"step_number": 5, "step_type": "TOOL_CALL", "tool_name": "tool_a", "tool_arguments": {"a": 3}},
        {"step_number": 6, "step_type": "TOOL_CALL", "tool_name": "tool_b", "tool_arguments": {"b": 3}},
    ]
    res = detector.detect(steps)
    assert res["is_loop_detected"] is True
    assert res["loop_type"] == "CYCLIC_TOOL_SEQUENCE"
    assert "tool_a -> tool_b" in res["explanation"]


def test_loop_detector_clean_trajectory():
    """Progressing trajectories with diverse calls do not flag loops."""
    detector = LoopDetector()
    steps = [
        {"step_number": 1, "step_type": "MODEL_REQUEST"},
        {"step_number": 2, "step_type": "TOOL_CALL", "tool_name": "search", "tool_arguments": {"q": "news"}},
        {"step_number": 3, "step_type": "TOOL_RESULT", "tool_name": "search"},
        {"step_number": 4, "step_type": "TOOL_CALL", "tool_name": "filter", "tool_arguments": {"limit": 5}},
        {"step_number": 5, "step_type": "TOOL_RESULT", "tool_name": "filter"},
        {"step_number": 6, "step_type": "TOOL_CALL", "tool_name": "summarize", "tool_arguments": {"len": 100}},
        {"step_number": 7, "step_type": "FINAL", "status": "SUCCESS"},
    ]
    res = detector.detect(steps)
    assert res["is_loop_detected"] is False
    assert res["loop_count"] == 0


def test_tool_evaluator_schema_validation():
    """ToolEvaluator validates arguments against input JSON schema."""
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1},
        },
        "required": ["query"],
    }
    # Valid
    ok, err = ToolEvaluator.validate_arguments(schema, {"query": "deep learning", "top_k": 3})
    assert ok is True
    assert err is None

    # Missing required
    ok, err = ToolEvaluator.validate_arguments(schema, {"top_k": 3})
    assert ok is False
    assert "query" in err

    # Wrong type
    ok, err = ToolEvaluator.validate_arguments(schema, {"query": "test", "top_k": "invalid_int"})
    assert ok is False
    assert "is not of type 'integer'" in err


def test_tool_evaluator_forbidden_tool():
    """Forbidden tool invocation returns FAIL and is_blocking=True."""
    res = ToolEvaluator.evaluate_tool_selection(
        actual_tool_name="delete_database",
        expected_tools=["search", "calculate"],
        forbidden_tools=["delete_database", "drop_table"],
    )
    assert res["status"] == "FAIL"
    assert res["is_blocking"] is True
    assert "CRITICAL SAFETY VIOLATION" in res["reason"]


def test_tool_evaluator_sensitive_redaction():
    """Sensitive keys (password, api_key, token, secret) are redacted."""
    raw_payload = {
        "user": "alice",
        "api_key": "sk-1234567890",
        "nested": {
            "password": "supersecretpassword",
            "token": "bearer_987654",
            "normal_field": "public_data",
        },
    }
    redacted = redact_sensitive_data(raw_payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["normal_field"] == "public_data"


def test_trajectory_evaluator_recovery():
    """TrajectoryEvaluator detects failure followed by recovery."""
    evaluator = TrajectoryEvaluator()
    task = {
        "max_steps": 10,
        "max_tool_calls": 10,
        "expected_tools": ["fetch_data"],
        "forbidden_tools": [],
    }
    steps = [
        {"step_number": 1, "step_type": "MODEL_REQUEST"},
        {"step_number": 2, "step_type": "TOOL_CALL", "tool_name": "fetch_data"},
        {"step_number": 3, "step_type": "TOOL_RESULT", "status": "FAIL", "error_message": "Timeout"},
        {"step_number": 4, "step_type": "TOOL_CALL", "tool_name": "fetch_data"},
        {"step_number": 5, "step_type": "TOOL_RESULT", "status": "SUCCESS", "tool_result": {"items": [1]}},
        {"step_number": 6, "step_type": "FINAL", "status": "SUCCESS"},
    ]
    res = evaluator.evaluate(steps=steps, task=task)
    assert res["metrics"]["failed_tool_calls"] == 1
    assert res["metrics"]["recovered_failures"] == 1
    assert res["metrics"]["unrecovered_failures"] == 0
    assert res["metrics"]["recovery_rate"] == 1.0

    recovery_check = next(c for c in res["checks"] if c["check_name"] == "failure_recovery")
    assert recovery_check["status"] == "PASS"


def test_agent_reliability_scoring_and_blocking_invariant():
    """Safety blocking rules override score, setting safety_status='BLOCKED'."""
    scorer = AgentReliabilityScorer()

    # Case 1: High quality run without safety violations
    eval_results_clean = {
        "overall_status": "PASS",
        "metrics": {
            "total_steps": 5,
            "total_tool_calls": 3,
            "failed_tool_calls": 0,
            "recovered_failures": 0,
            "unrecovered_failures": 0,
            "loops_detected": 0,
            "safety_violations": 0,
            "recovery_rate": 1.0,
        },
    }
    score, breakdown, safety = scorer.compute_score(
        goal_status="COMPLETED",
        evaluation_results=eval_results_clean,
    )
    assert score == 100.0
    assert safety == "PASS"
    assert breakdown["dimensions"]["goal_completion"]["score"] == 100.0

    # Case 2: Run with 1 safety violation -> Must be BLOCKED regardless of score
    eval_results_violation = {
        "overall_status": "BLOCKED",
        "metrics": {
            "total_steps": 5,
            "total_tool_calls": 3,
            "failed_tool_calls": 0,
            "recovered_failures": 0,
            "unrecovered_failures": 0,
            "loops_detected": 0,
            "safety_violations": 1,
            "recovery_rate": 1.0,
        },
    }
    score_v, breakdown_v, safety_v = scorer.compute_score(
        goal_status="COMPLETED",
        evaluation_results=eval_results_violation,
    )
    assert safety_v == "BLOCKED"
    assert breakdown_v["safety_status"] == "BLOCKED"


def test_compute_agent_fingerprint_deterministic():
    """Agent configuration fingerprint is deterministic across same configurations."""
    fp1 = compute_agent_fingerprint(
        agent_name="Analyst",
        agent_type="TOOL_AGENT",
        version=1,
        system_prompt="Analyze data.",
        tool_manifest=[{"name": "search"}],
    )
    fp2 = compute_agent_fingerprint(
        agent_name="Analyst",
        agent_type="TOOL_AGENT",
        version=1,
        system_prompt="Analyze data.",
        tool_manifest=[{"name": "search"}],
    )
    assert fp1 == fp2
    assert len(fp1) == 64
