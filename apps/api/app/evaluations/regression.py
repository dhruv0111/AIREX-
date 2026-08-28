"""Regression detection and classification engine (Phase 6).

Classifies metric comparisons into IMPROVED, REGRESSED, NO_SIGNIFICANT_CHANGE,
and determines the severity (NONE, LOW, MEDIUM, HIGH, CRITICAL) of regressions.
"""

from __future__ import annotations

from typing import Any

# Direction mappings
HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
LOWER_IS_BETTER = "LOWER_IS_BETTER"

# Metric directions
METRIC_DIRECTIONS = {
    "accuracy": HIGHER_IS_BETTER,
    "quality_score": HIGHER_IS_BETTER,
    "pass_rate": HIGHER_IS_BETTER,
    "combined_score": HIGHER_IS_BETTER,
    "judge_score": HIGHER_IS_BETTER,
    "hallucination_rate": LOWER_IS_BETTER,
    "failure_rate": LOWER_IS_BETTER,
    "error_rate": LOWER_IS_BETTER,
    "latency": LOWER_IS_BETTER,
    "latency_ms": LOWER_IS_BETTER,
    "token_usage": LOWER_IS_BETTER,
    "estimated_cost": LOWER_IS_BETTER,
    "cost": LOWER_IS_BETTER,
}


def get_metric_direction(metric_name: str) -> str:
    name_lower = metric_name.lower()
    for key, direction in METRIC_DIRECTIONS.items():
        if key in name_lower:
            return direction
    return HIGHER_IS_BETTER


def classify_comparison(
    metric_name: str,
    baseline_value: float | None,
    candidate_value: float | None,
    p_value: float | None = None,
    tolerance: float = 1e-6,
) -> str:
    """Classify comparison as IMPROVED, REGRESSED, NO_SIGNIFICANT_CHANGE, or INCONCLUSIVE."""
    if baseline_value is None or candidate_value is None:
        return "INCONCLUSIVE"

    direction = get_metric_direction(metric_name)
    diff = candidate_value - baseline_value

    # If t-test p-value is available and valid, we use statistical significance.
    if p_value is not None:
        if p_value < 0.05:
            if direction == HIGHER_IS_BETTER:
                return "IMPROVED" if diff > 0 else "REGRESSED"
            else:
                return "IMPROVED" if diff < 0 else "REGRESSED"
        else:
            return "NO_SIGNIFICANT_CHANGE"

    # Fallback to direct numerical difference
    if abs(diff) <= tolerance:
        return "NO_SIGNIFICANT_CHANGE"

    if direction == HIGHER_IS_BETTER:
        return "IMPROVED" if diff > 0 else "REGRESSED"
    else:
        return "IMPROVED" if diff < 0 else "REGRESSED"


def calculate_severity(
    metric_name: str,
    baseline_value: float | None,
    candidate_value: float | None,
    classification: str,
) -> str:
    """Calculate regression severity (NONE, LOW, MEDIUM, HIGH, CRITICAL)."""
    if classification != "REGRESSED" or baseline_value is None or candidate_value is None:
        return "NONE"

    direction = get_metric_direction(metric_name)

    # Calculate degradation percentage
    if direction == HIGHER_IS_BETTER:
        # Lower is worse, so candidate < baseline. Drop percentage:
        if baseline_value > 0:
            degradation = (baseline_value - candidate_value) / baseline_value
        else:
            degradation = 0.0
    else:
        # Higher is worse, so candidate > baseline. Increase percentage:
        if baseline_value > 0:
            degradation = (candidate_value - baseline_value) / baseline_value
        else:
            degradation = 0.0

    if degradation <= 0.02:
        return "NONE"
    elif degradation <= 0.05:
        return "LOW"
    elif degradation <= 0.15:
        return "MEDIUM"
    elif degradation <= 0.30:
        return "HIGH"
    else:
        return "CRITICAL"


def analyze_regression(
    metric_name: str,
    baseline_value: float | None,
    candidate_value: float | None,
    p_value: float | None = None,
) -> dict[str, Any]:
    """Perform complete regression analysis for a single metric."""
    classification = classify_comparison(metric_name, baseline_value, candidate_value, p_value)
    severity = calculate_severity(metric_name, baseline_value, candidate_value, classification)

    diff = None
    rel_diff = None
    if baseline_value is not None and candidate_value is not None:
        diff = candidate_value - baseline_value
        rel_diff = diff / baseline_value if baseline_value > 0 else 0.0

    return {
        "metric_name": metric_name,
        "baseline_value": baseline_value,
        "candidate_value": candidate_value,
        "absolute_difference": diff,
        "relative_difference": rel_diff,
        "classification": classification,
        "severity": severity,
        "direction": get_metric_direction(metric_name),
    }
