"""Simple, explainable anomaly detection helpers (Phase 8 §40).

Implements three non-ML strategies:

- ``threshold``: a fixed threshold comparison with an operator.
- ``moving_average``: deviation of the current value from a trailing moving
  average by a configurable relative factor (e.g. +30%).
- ``standard_deviation``: deviation of the current value from the historical
  mean expressed in standard deviations (z-score).

All functions are pure and deterministic, which keeps them unit-testable and
explainable in alert messages.
"""

from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Sequence


def threshold_check(
    value: float,
    threshold: float,
    operator: str = ">",
) -> bool:
    """Return True when ``value`` crosses ``threshold`` using ``operator``."""
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == "==":
        return value == threshold
    raise ValueError(f"Unsupported operator: {operator}")


def moving_average_detection(
    history: Sequence[float],
    current: float,
    *,
    window: int = 10,
    deviation_factor: float = 0.3,
) -> dict:
    """Flag when ``current`` deviates from the trailing moving average.

    Example (spec §40):
        p95 baseline 800ms, current 1300ms, threshold +30% -> anomaly.
    """
    if not history:
        return {
            "is_anomaly": False,
            "baseline": None,
            "deviation": None,
            "reason": "insufficient_history",
        }

    recent = list(history)[-window:]
    baseline = mean(recent)

    if baseline == 0:
        deviation = None
    else:
        deviation = (current - baseline) / baseline

    is_anomaly = deviation is not None and deviation >= deviation_factor

    return {
        "is_anomaly": is_anomaly,
        "baseline": baseline,
        "deviation": deviation,
        "reason": (
            f"current={current:.4f} exceeds moving average {baseline:.4f} "
            f"by {deviation * 100:.1f}% (factor {deviation_factor * 100:.0f}%)"
            if is_anomaly
            else "within_moving_average"
        ),
    }


def standard_deviation_detection(
    history: Sequence[float],
    current: float,
    *,
    z_score_threshold: float = 3.0,
) -> dict:
    """Flag when ``current`` is more than ``z_score_threshold`` stddevs from the mean."""
    if len(history) < 2:
        return {
            "is_anomaly": False,
            "baseline": None,
            "z_score": None,
            "reason": "insufficient_history",
        }

    baseline = mean(history)
    std = pstdev(history)

    if std == 0:
        z_score = 0.0
    else:
        z_score = (current - baseline) / std

    is_anomaly = abs(z_score) >= z_score_threshold

    return {
        "is_anomaly": is_anomaly,
        "baseline": baseline,
        "z_score": z_score,
        "reason": (
            f"current={current:.4f} is {z_score:.2f} standard deviations from "
            f"mean {baseline:.4f} (threshold {z_score_threshold})"
            if is_anomaly
            else "within_standard_deviation"
        ),
    }


def detect_anomaly(
    history: Sequence[float],
    current: float,
    *,
    method: str = "threshold",
    threshold: float = 0.0,
    operator: str = ">",
    window: int = 10,
    deviation_factor: float = 0.3,
    z_score_threshold: float = 3.0,
) -> dict:
    """Dispatch to a named anomaly detection strategy."""
    method = method.lower()
    if method == "threshold":
        crossed = threshold_check(current, threshold, operator)
        return {
            "is_anomaly": crossed,
            "baseline": threshold,
            "reason": (
                f"current={current:.4f} {operator} threshold={threshold:.4f}"
                if crossed
                else "within_threshold"
            ),
        }
    if method in ("moving_average", "moving-average"):
        return moving_average_detection(
            history, current, window=window, deviation_factor=deviation_factor
        )
    if method in ("standard_deviation", "stddev", "zscore"):
        return standard_deviation_detection(history, current, z_score_threshold=z_score_threshold)
    raise ValueError(f"Unsupported anomaly detection method: {method}")
