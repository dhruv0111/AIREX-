"""Unit tests for Phase 10 Decision Engine, Fingerprinting, Readiness Scoring, and Recommendations."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from uuid import uuid4
import pytest

from app.models.release_decision import ReleasePolicy
from app.services.decision_engine import DecisionEngine
from app.services.fingerprint import compute_configuration_fingerprint


def _make_dummy_policy(**kwargs) -> ReleasePolicy:
    return ReleasePolicy(
        id=uuid4(),
        project_id=uuid4(),
        environment_id=uuid4(),
        name="Test Policy",
        version=1,
        min_reliability_score=kwargs.get("min_reliability_score", 85.0),
        max_regression_severity=kwargs.get("max_regression_severity", "HIGH"),
        max_error_rate=kwargs.get("max_error_rate", 0.01),
        max_latency_ms=kwargs.get("max_latency_ms", 1000.0),
        max_p95_latency_ms=kwargs.get("max_p95_latency_ms", 3000.0),
        max_cost=kwargs.get("max_cost", 0.05),
        max_critical_alerts=kwargs.get("max_critical_alerts", 0),
        min_statistical_confidence=kwargs.get("min_statistical_confidence", 0.95),
        min_sample_size=kwargs.get("min_sample_size", 100),
        required_benchmark=kwargs.get("required_benchmark", True),
        required_evaluation=kwargs.get("required_evaluation", True),
        max_evidence_age_days=kwargs.get("max_evidence_age_days", 14),
    )


def test_configuration_fingerprint_determinism():
    model_id = uuid4()
    provider_id = uuid4()
    env_id = uuid4()
    config = {"temperature": 0.2, "top_p": 0.9}

    fp1 = compute_configuration_fingerprint(
        model_id=model_id,
        provider_id=provider_id,
        environment_id=env_id,
        model_version="1.0",
        model_configuration=config,
        policy_version=1,
    )
    fp2 = compute_configuration_fingerprint(
        model_id=model_id,
        provider_id=provider_id,
        environment_id=env_id,
        model_version="1.0",
        model_configuration=config,
        policy_version=1,
    )
    assert fp1 == fp2
    assert len(fp1) == 64

    # Change in policy version must yield different fingerprint
    fp3 = compute_configuration_fingerprint(
        model_id=model_id,
        provider_id=provider_id,
        environment_id=env_id,
        model_version="1.0",
        model_configuration=config,
        policy_version=2,
    )
    assert fp1 != fp3


def test_decision_engine_approved_outcome():
    policy = _make_dummy_policy(
        min_reliability_score=85.0,
        max_critical_alerts=0,
        max_regression_severity="HIGH",
    )
    engine = DecisionEngine(policy)

    evidences = [
        {
            "source_type": "EVALUATION",
            "source_id": "eval-1",
            "is_fresh": True,
            "freshness_timestamp": datetime.now(UTC),
            "summary": {
                "total_tests": 120,
                "passed_tests": 115,
                "accuracy_score": 95.8,
            },
        },
        {
            "source_type": "BENCHMARK",
            "source_id": "bench-1",
            "is_fresh": True,
            "freshness_timestamp": datetime.now(UTC),
            "summary": {
                "reliability_score": 91.4,
                "sample_size": 150,
                "statistical_confidence": 0.98,
            },
        },
        {
            "source_type": "EXPERIMENT",
            "source_id": "exp-1",
            "is_fresh": True,
            "freshness_timestamp": datetime.now(UTC),
            "summary": {
                "max_regression_severity": "LOW",
                "quality_gates_passed": True,
            },
        },
        {
            "source_type": "OBSERVABILITY",
            "source_id": "obs-1",
            "is_fresh": True,
            "freshness_timestamp": datetime.now(UTC),
            "summary": {
                "error_rate": 0.002,
                "p95_latency_ms": 1200.0,
                "availability": 0.998,
            },
        },
        {
            "source_type": "ALERT",
            "source_id": "alert-1",
            "is_fresh": True,
            "freshness_timestamp": datetime.now(UTC),
            "summary": {
                "total_active_alerts": 0,
                "critical_alerts_count": 0,
            },
        },
    ]

    res = engine.evaluate(evidences, model_id=uuid4(), environment_id=uuid4())
    assert res["outcome"] == "APPROVED"
    assert res["readiness_score"] >= 85.0
    assert any(r["type"] == "PROCEED" for r in res["recommendations"])


def test_decision_engine_blocked_by_critical_alert():
    policy = _make_dummy_policy(max_critical_alerts=0)
    engine = DecisionEngine(policy)

    evidences = [
        {
            "source_type": "EVALUATION",
            "source_id": "eval-1",
            "is_fresh": True,
            "summary": {"total_tests": 100, "accuracy_score": 99.0},
        },
        {
            "source_type": "BENCHMARK",
            "source_id": "bench-1",
            "is_fresh": True,
            "summary": {"reliability_score": 99.0, "sample_size": 200, "statistical_confidence": 0.99},
        },
        {
            "source_type": "ALERT",
            "source_id": "alert-1",
            "is_fresh": True,
            "summary": {"total_active_alerts": 1, "critical_alerts_count": 1},
        },
    ]

    res = engine.evaluate(evidences, model_id=uuid4(), environment_id=uuid4())
    assert res["outcome"] == "BLOCKED"
    crit_check = next(c for c in res["checks"] if c["rule_name"] == "critical_alerts")
    assert crit_check["status"] == "FAIL"
    assert crit_check["is_blocking"] is True
    # Blocking rules MUST override high readiness score
    assert any(r["type"] == "BLOCK_ACTION" for r in res["recommendations"])


def test_decision_engine_insufficient_evidence():
    policy = _make_dummy_policy(required_benchmark=True, required_evaluation=True)
    engine = DecisionEngine(policy)

    # Empty evidences list
    res = engine.evaluate([], model_id=uuid4(), environment_id=uuid4())
    assert res["outcome"] in ("INSUFFICIENT_EVIDENCE", "BLOCKED")
    assert any(c["status"] == "MISSING" for c in res["checks"])


def test_decision_engine_rejected_by_low_reliability():
    policy = _make_dummy_policy(min_reliability_score=85.0)
    engine = DecisionEngine(policy)

    evidences = [
        {
            "source_type": "EVALUATION",
            "source_id": "eval-1",
            "is_fresh": True,
            "summary": {"total_tests": 100, "accuracy_score": 80.0},
        },
        {
            "source_type": "BENCHMARK",
            "source_id": "bench-1",
            "is_fresh": True,
            "summary": {"reliability_score": 72.0, "sample_size": 100, "statistical_confidence": 0.96},
        },
        {
            "source_type": "ALERT",
            "source_id": "alert-1",
            "is_fresh": True,
            "summary": {"critical_alerts_count": 0},
        },
    ]

    res = engine.evaluate(evidences, model_id=uuid4(), environment_id=uuid4())
    assert res["outcome"] == "REJECTED"
    rel_check = next(c for c in res["checks"] if c["rule_name"] == "min_reliability_score")
    assert rel_check["status"] == "FAIL"


def test_decision_engine_conditionally_approved_on_stale_data():
    policy = _make_dummy_policy(min_reliability_score=80.0)
    engine = DecisionEngine(policy)

    evidences = [
        {
            "source_type": "EVALUATION",
            "source_id": "eval-1",
            "is_fresh": True,
            "summary": {"total_tests": 100, "accuracy_score": 85.0},
        },
        {
            "source_type": "BENCHMARK",
            "source_id": "bench-1",
            "is_fresh": False,  # Stale
            "freshness_timestamp": datetime.now(UTC) - timedelta(days=20),
            "summary": {"reliability_score": 88.0, "sample_size": 100, "statistical_confidence": 0.95},
        },
        {
            "source_type": "ALERT",
            "source_id": "alert-1",
            "is_fresh": True,
            "summary": {"critical_alerts_count": 0},
        },
    ]

    res = engine.evaluate(evidences, model_id=uuid4(), environment_id=uuid4())
    assert res["outcome"] == "CONDITIONALLY_APPROVED"
    assert any(c["status"] == "STALE" for c in res["checks"])


def test_readiness_score_dimensions_and_weights():
    policy = _make_dummy_policy()
    engine = DecisionEngine(policy)

    eval_ev = {"summary": {"accuracy_score": 90.0}}
    bench_ev = {"summary": {"reliability_score": 85.0}}
    exp_ev = {"summary": {"max_regression_severity": "LOW"}}
    obs_ev = {"summary": {"availability": 0.99, "p95_latency_ms": 500.0}}
    alert_ev = {"summary": {"critical_alerts_count": 0, "total_active_alerts": 0}}

    score, breakdown = engine._compute_readiness_score(eval_ev, exp_ev, bench_ev, obs_ev, alert_ev)
    assert 0.0 <= score <= 100.0
    total_weight = sum(v["weight"] for v in breakdown.values())
    assert abs(total_weight - 1.0) < 0.001
