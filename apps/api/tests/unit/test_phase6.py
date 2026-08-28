"""Unit tests for Phase 6 statistical comparison, regressions and quality gates."""

from __future__ import annotations

import math
import pytest
from app.evaluations.statistics import (
    calculate_mean,
    calculate_median,
    calculate_variance,
    calculate_std_dev,
    calculate_margin_of_error,
    calculate_comparison_statistics,
)
from app.evaluations.regression import classify_comparison, calculate_severity, analyze_regression
from app.evaluations.gates import evaluate_gate, compute_overall_gate_status


def test_statistics_helpers():
    # Test mean & median
    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert calculate_mean(data) == 3.0
    assert calculate_median(data) == 3.0

    data_even = [1.0, 2.0, 3.0, 4.0]
    assert calculate_mean(data_even) == 2.5
    assert calculate_median(data_even) == 2.5

    # Test variance & std dev
    assert calculate_variance(data) == 2.5
    assert calculate_std_dev(data) == math.sqrt(2.5)

    # Test margin of error
    margin = calculate_margin_of_error(math.sqrt(2.5), 5)
    assert margin > 0.0


def test_statistics_welch_t_test():
    # Two distinct samples
    baseline = [10.0, 11.0, 12.0, 10.0, 11.0]
    candidate = [15.0, 16.0, 14.0, 15.0, 16.0]

    stats = calculate_comparison_statistics(baseline, candidate)
    assert stats is not None
    assert stats["sample_size_baseline"] == 5
    assert stats["sample_size_candidate"] == 5
    assert stats["mean_baseline"] == 10.8
    assert stats["mean_candidate"] == 15.2
    assert stats["effect_size"] > 0
    assert stats["p_value"] < 0.05  # highly significant difference

    # Identical samples
    stats_same = calculate_comparison_statistics(baseline, baseline)
    assert stats_same is not None
    assert stats_same["p_value"] == 1.0
    assert stats_same["effect_size"] == 0.0

    # Small samples
    stats_small = calculate_comparison_statistics([1.0, 2.0], [3.0, 4.0])
    assert stats_small is None


def test_regression_classification():
    # HIGHER_IS_BETTER (e.g. accuracy)
    # Improvement
    assert classify_comparison("accuracy", 0.90, 0.94) == "IMPROVED"
    # Regression
    assert classify_comparison("accuracy", 0.90, 0.84) == "REGRESSED"
    # No significant change
    assert classify_comparison("accuracy", 0.90, 0.90) == "NO_SIGNIFICANT_CHANGE"

    # LOWER_IS_BETTER (e.g. hallucination_rate, latency)
    # Improvement
    assert classify_comparison("hallucination_rate", 0.10, 0.05) == "IMPROVED"
    assert classify_comparison("latency", 1000.0, 700.0) == "IMPROVED"
    # Regression
    assert classify_comparison("hallucination_rate", 0.05, 0.10) == "REGRESSED"
    assert classify_comparison("latency", 700.0, 1200.0) == "REGRESSED"

    # Inconclusive
    assert classify_comparison("accuracy", None, 0.90) == "INCONCLUSIVE"
    assert classify_comparison("accuracy", 0.90, None) == "INCONCLUSIVE"


def test_regression_severity():
    # No regression
    assert calculate_severity("accuracy", 0.90, 0.95, "IMPROVED") == "NONE"
    assert calculate_severity("accuracy", 0.90, 0.90, "NO_SIGNIFICANT_CHANGE") == "NONE"

    # Regression severity for higher is better (accuracy)
    # 0.90 -> 0.89 (1.1% drop) -> NONE
    assert calculate_severity("accuracy", 0.90, 0.89, "REGRESSED") == "NONE"
    # 0.90 -> 0.86 (4.4% drop) -> LOW
    assert calculate_severity("accuracy", 0.90, 0.86, "REGRESSED") == "LOW"
    # 0.90 -> 0.80 (11.1% drop) -> MEDIUM
    assert calculate_severity("accuracy", 0.90, 0.80, "REGRESSED") == "MEDIUM"
    # 0.90 -> 0.70 (22.2% drop) -> HIGH
    assert calculate_severity("accuracy", 0.90, 0.70, "REGRESSED") == "HIGH"
    # 0.90 -> 0.50 (44.4% drop) -> CRITICAL
    assert calculate_severity("accuracy", 0.90, 0.50, "REGRESSED") == "CRITICAL"


def test_quality_gates():
    # Evaluate individual gate
    comp = {
        "candidate_value": 0.94,
        "absolute_difference": 0.04,
        "relative_difference": 0.044,
    }

    # GT / GTE
    status, val = evaluate_gate("CANDIDATE_VALUE", "GTE", 0.90, comp)
    assert status == "PASS"
    assert val == 0.94

    status, val = evaluate_gate("CANDIDATE_VALUE", "LT", 0.90, comp)
    assert status == "FAIL"

    status, val = evaluate_gate("CANDIDATE_VALUE", "GTE", 0.95, comp)
    assert status == "FAIL"

    # Relative change
    status, val = evaluate_gate("RELATIVE_CHANGE", "GTE", 0.0, comp)
    assert status == "PASS"

    # Inconclusive
    status, val = evaluate_gate("CANDIDATE_VALUE", "GTE", 0.90, None)
    assert status == "INCONCLUSIVE"


def test_overall_gate_status():
    # All required gates pass -> PASS
    results = [
        {"is_required": True, "status": "PASS"},
        {"is_required": True, "status": "PASS"},
        {"is_required": False, "status": "FAIL"},  # optional gate fail doesn't fail overall
    ]
    assert compute_overall_gate_status(results) == "PASS"

    # Required gate fails -> FAIL
    results_fail = [
        {"is_required": True, "status": "PASS"},
        {"is_required": True, "status": "FAIL"},
    ]
    assert compute_overall_gate_status(results_fail) == "FAIL"

    # Required gate inconclusive -> INCONCLUSIVE
    results_inc = [
        {"is_required": True, "status": "PASS"},
        {"is_required": True, "status": "INCONCLUSIVE"},
    ]
    assert compute_overall_gate_status(results_inc) == "INCONCLUSIVE"

    # Optional gates only
    results_opt = [
        {"is_required": False, "status": "FAIL"},
    ]
    assert compute_overall_gate_status(results_opt) == "PASS"
