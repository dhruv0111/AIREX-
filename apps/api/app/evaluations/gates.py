"""Quality gates evaluation engine (Phase 6).

Evaluates comparison results against quality gate rules to output
PASS, FAIL, or INCONCLUSIVE for each gate and compute the overall run gate outcome.
"""

from __future__ import annotations

from typing import Any


def evaluate_gate(
    gate_type: str,
    operator: str,
    threshold: float,
    comparison: dict[str, Any] | None,
) -> tuple[str, float | None]:
    """Evaluate a single quality gate.

    Returns a tuple of (status, actual_value).
    """
    if comparison is None:
        return "INCONCLUSIVE", None

    actual_val: float | None = None
    if gate_type == "CANDIDATE_VALUE":
        actual_val = comparison.get("candidate_value")
    elif gate_type == "ABSOLUTE_CHANGE":
        actual_val = comparison.get("absolute_difference")
    elif gate_type == "RELATIVE_CHANGE":
        actual_val = comparison.get("relative_difference")

    if actual_val is None:
        return "INCONCLUSIVE", None

    op = operator.upper()
    passed = False

    if op == "GT":
        passed = actual_val > threshold
    elif op == "GTE":
        passed = actual_val >= threshold
    elif op == "LT":
        passed = actual_val < threshold
    elif op == "LTE":
        passed = actual_val <= threshold
    elif op == "EQ":
        passed = abs(actual_val - threshold) < 1e-9
    else:
        return "INCONCLUSIVE", actual_val

    status = "PASS" if passed else "FAIL"
    return status, actual_val


def compute_overall_gate_status(gate_results: list[dict[str, Any]]) -> str:
    """Determine the overall quality gate result (PASS, FAIL, INCONCLUSIVE).

    Rules:
      - Any required gate FAIL -> overall FAIL
      - Any required gate INCONCLUSIVE (and no FAIL) -> overall INCONCLUSIVE
      - All required gates PASS -> overall PASS
      - Optional gates do not fail or make the overall result inconclusive.
    """
    has_required_fail = False
    has_required_inconclusive = False
    has_required_gates = False

    for res in gate_results:
        is_req = res.get("is_required", True)
        status = res.get("status", "INCONCLUSIVE")

        if is_req:
            has_required_gates = True
            if status == "FAIL":
                has_required_fail = True
            elif status == "INCONCLUSIVE":
                has_required_inconclusive = True

    if not has_required_gates:
        return "PASS"

    if has_required_fail:
        return "FAIL"

    if has_required_inconclusive:
        return "INCONCLUSIVE"

    return "PASS"
