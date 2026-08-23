"""Evaluation metric aggregation (Phase 3 §31–§32; Phase 4 §39–§41)."""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from typing import Any


def _percentile(sorted_values: list[float], percentile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def compute_run_metrics(results: Iterable[Any]) -> dict[str, Any]:
    """Aggregate per-run metrics from result rows (Phase 3 §31).

    ``results`` are ORM EvaluationResult objects (status, latency_ms,
    input_tokens, output_tokens, total_tokens).
    """
    rows = list(results)
    total = len(rows)
    passed = sum(1 for r in rows if r.status == "PASS")
    failed = sum(1 for r in rows if r.status == "FAIL")
    errors = sum(1 for r in rows if r.status == "ERROR")
    skipped = sum(1 for r in rows if r.status == "SKIPPED")

    latencies = sorted(float(r.latency_ms) for r in rows if r.latency_ms is not None)
    total_input = sum(r.input_tokens or 0 for r in rows)
    total_output = sum(r.output_tokens or 0 for r in rows)
    total_tokens = sum(r.total_tokens or 0 for r in rows)

    metrics: dict[str, Any] = {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "fail_rate": round(failed / total, 4) if total else 0.0,
        "error_rate": round(errors / total, 4) if total else 0.0,
        "average_latency_ms": round(statistics.fmean(latencies), 2) if latencies else None,
        "p50_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
    }

    judge_scores = [float(v) for r in rows if (v := getattr(r, "judge_score", None)) is not None]
    judge_confidences = [
        float(v) for r in rows if (v := getattr(r, "judge_confidence", None)) is not None
    ]
    if judge_scores:
        metrics["average_judge_score"] = round(statistics.fmean(judge_scores), 4)
        metrics["judge_pass_rate"] = round(
            sum(1 for s in judge_scores if s >= 0.75) / len(judge_scores), 4
        )
        metrics["average_confidence"] = (
            round(statistics.fmean(judge_confidences), 4) if judge_confidences else None
        )
        # Per-criterion averages follow the rubric dynamically (Phase 4 §39).
        criteria_totals: dict[str, list[float]] = {}
        for row in rows:
            for name, value in (getattr(row, "judge_criteria_scores", None) or {}).items():
                criteria_totals.setdefault(name, []).append(float(value))
        metrics["judge_criteria"] = {
            name: round(statistics.fmean(values), 4) for name, values in criteria_totals.items()
        }
    return metrics


def compute_evaluator_metrics(results: Iterable[Any]) -> dict[str, dict[str, Any]]:
    """Per-evaluator metrics (Phase 3 §32) from result ``score`` JSON.

    Each result's ``score`` is a list of ``{evaluator, version, score, passed,
    reason}`` dicts.
    """
    by_evaluator: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        score_list = result.score if isinstance(result.score, list) else []
        for entry in score_list:
            if not isinstance(entry, dict):
                continue
            name = entry.get("evaluator")
            if not name:
                continue
            by_evaluator.setdefault(name, []).append(entry)

    aggregated: dict[str, dict[str, Any]] = {}
    for name, entries in by_evaluator.items():
        count = len(entries)
        passed = sum(1 for e in entries if e.get("passed"))
        failed = count - passed
        avg_score = (
            statistics.fmean(float(e.get("score", 0.0)) for e in entries) if entries else 0.0
        )
        aggregated[name] = {
            "count": count,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / count, 4) if count else 0.0,
            "average_score": round(avg_score, 4),
        }
    return aggregated


def apply_pass_policy(
    scores: Sequence[dict[str, Any]],
    *,
    pass_policy: str = "ALL",
    threshold: float | None = None,
    weights: Sequence[float | None] | None = None,
) -> tuple[bool, float | None]:
    """Determine the combined pass decision (Phase 4 §41–§42).

    ``scores`` are asdict(EvaluationScore) entries. Individual scores are never
    replaced; the combined decision is returned as ``(passed, combined_score)``.

    - ANY: pass if any evaluator passed (combined score None).
    - ALL: pass only if every evaluator passed (combined score None).
    - WEIGHTED: normalized weighted mean of individual scores vs ``threshold``
      (default 0.5 when unspecified).
    """
    if not scores:
        return False, None
    policy = (pass_policy or "ALL").upper()
    if policy == "ANY":
        return any(s.get("passed") for s in scores), None
    if policy == "WEIGHTED":
        raw = [float(w) if w is not None else 1.0 for w in (weights or [])]
        raw = (raw + [1.0] * (len(scores) - len(raw)))[: len(scores)]
        total = sum(raw)
        normalized = [w / total for w in raw] if total > 0 else [1.0 / len(scores)] * len(scores)
        combined = sum(s.get("score", 0.0) * w for s, w in zip(scores, normalized, strict=True))
        t = float(threshold) if threshold is not None else 0.5
        return combined >= t, combined
    # ALL (default)
    return all(s.get("passed") for s in scores), None
