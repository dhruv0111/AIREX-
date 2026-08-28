"""Core statistical comparison engine (pure Python; Phase 6).

Implements mean, median, standard deviation, effect size (Cohen's d), and
Welch's t-test (p-value using normal approximation with math.erf) for
independent samples of metric observations.
"""

from __future__ import annotations

import math
from typing import Any


def calculate_mean(data: list[float]) -> float:
    if not data:
        return 0.0
    return sum(data) / len(data)


def calculate_median(data: list[float]) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def calculate_variance(data: list[float], mean_val: float | None = None) -> float:
    n = len(data)
    if n < 2:
        return 0.0
    if mean_val is None:
        mean_val = calculate_mean(data)
    return sum((x - mean_val) ** 2 for x in data) / (n - 1)


def calculate_std_dev(data: list[float], mean_val: float | None = None) -> float:
    return math.sqrt(calculate_variance(data, mean_val))


def calculate_margin_of_error(std_dev: float, n: int, confidence_level: float = 0.95) -> float:
    if n < 2 or std_dev == 0:
        return 0.0
    # Standard normal Z-score for 95% confidence is 1.96
    z = 1.96
    return z * (std_dev / math.sqrt(n))


def calculate_comparison_statistics(
    baseline: list[float], candidate: list[float]
) -> dict[str, Any] | None:
    """Calculate statistical comparison metrics.

    Returns None if there is insufficient data (e.g. either sample size < 5).
    """
    n1 = len(baseline)
    n2 = len(candidate)

    if n1 < 5 or n2 < 5:
        # Insufficient data for meaningful statistical test
        return None

    m1 = calculate_mean(baseline)
    m2 = calculate_mean(candidate)

    med1 = calculate_median(baseline)
    med2 = calculate_median(candidate)

    v1 = calculate_variance(baseline, m1)
    v2 = calculate_variance(candidate, m2)

    std1 = math.sqrt(v1)
    std2 = math.sqrt(v2)

    margin1 = calculate_margin_of_error(std1, n1)
    margin2 = calculate_margin_of_error(std2, n2)

    # 1. Cohen's d (Effect Size)
    pooled_var = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
    pooled_std = math.sqrt(pooled_var)
    effect_size = (m2 - m1) / pooled_std if pooled_std > 0 else 0.0

    # 2. Welch's t-test p-value using Normal Approximation
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        t_stat = 0.0
        p_value = 0.0 if m1 != m2 else 1.0
    else:
        t_stat = (m2 - m1) / se
        # Normal approximation CDF (z-distribution)
        z = abs(t_stat)
        phi_z = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        p_value = 2.0 * (1.0 - phi_z)

    return {
        "sample_size_baseline": n1,
        "sample_size_candidate": n2,
        "mean_baseline": m1,
        "mean_candidate": m2,
        "median_baseline": med1,
        "median_candidate": med2,
        "std_dev_baseline": std1,
        "std_dev_candidate": std2,
        "ci_baseline_lower": m1 - margin1,
        "ci_baseline_upper": m1 + margin1,
        "ci_candidate_lower": m2 - margin2,
        "ci_candidate_upper": m2 + margin2,
        "effect_size": effect_size,
        "p_value": p_value,
        "t_statistic": t_stat,
    }
