"""Deterministic, explainable decision engine and deployment readiness scoring for Phase 10."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.release_decision import ReleasePolicy


class DecisionEngine:
    """Evaluates release policies against aggregated canonical evidence."""

    def __init__(self, policy: ReleasePolicy) -> None:
        self._policy = policy

    def evaluate(
        self,
        evidences: list[dict[str, Any]],
        *,
        model_id: UUID,
        environment_id: UUID,
    ) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        # Index evidence by source_type
        ev_map: dict[str, dict[str, Any]] = {e["source_type"]: e for e in evidences}

        eval_ev = ev_map.get("EVALUATION")
        exp_ev = ev_map.get("EXPERIMENT")
        bench_ev = ev_map.get("BENCHMARK")
        obs_ev = ev_map.get("OBSERVABILITY")
        alert_ev = ev_map.get("ALERT")
        agent_ev = ev_map.get("AGENT_EVALUATION")

        # ------------------------------------------------------------- 1. Required Evidence Availability
        if self._policy.required_evaluation:
            if not eval_ev:
                checks.append({
                    "rule_name": "required_evaluation",
                    "status": "MISSING",
                    "actual_value": None,
                    "expected_value": "Completed evaluation run",
                    "evidence_reference": None,
                    "explanation": "Release policy requires a completed evaluation run, but none was found for this model.",
                    "is_blocking": True,
                })
            else:
                checks.append({
                    "rule_name": "required_evaluation",
                    "status": "PASS",
                    "actual_value": eval_ev["source_id"],
                    "expected_value": "Completed evaluation run",
                    "evidence_reference": {"source_type": "EVALUATION", "source_id": eval_ev["source_id"]},
                    "explanation": f"Evaluation evidence found: run {eval_ev['source_id']}.",
                    "is_blocking": False,
                })

        if self._policy.required_benchmark:
            if not bench_ev:
                checks.append({
                    "rule_name": "required_benchmark",
                    "status": "MISSING",
                    "actual_value": None,
                    "expected_value": "Completed benchmark run",
                    "evidence_reference": None,
                    "explanation": "Release policy requires a completed benchmark run, but none was found.",
                    "is_blocking": True,
                })
            else:
                checks.append({
                    "rule_name": "required_benchmark",
                    "status": "PASS",
                    "actual_value": bench_ev["source_id"],
                    "expected_value": "Completed benchmark run",
                    "evidence_reference": {"source_type": "BENCHMARK", "source_id": bench_ev["source_id"]},
                    "explanation": f"Benchmark evidence found: run {bench_ev['source_id']}.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- 2. Evidence Freshness
        for ev in evidences:
            stype = ev["source_type"]
            is_fresh = ev.get("is_fresh", True)
            fresh_ts = ev.get("freshness_timestamp")
            if not is_fresh:
                checks.append({
                    "rule_name": f"freshness_{stype.lower()}",
                    "status": "STALE",
                    "actual_value": str(fresh_ts),
                    "expected_value": f"<= {self._policy.max_evidence_age_days} days old",
                    "evidence_reference": {"source_type": stype, "source_id": ev["source_id"]},
                    "explanation": f"{stype} evidence is older than the policy maximum of {self._policy.max_evidence_age_days} days.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": f"freshness_{stype.lower()}",
                    "status": "PASS",
                    "actual_value": str(fresh_ts),
                    "expected_value": f"<= {self._policy.max_evidence_age_days} days old",
                    "evidence_reference": {"source_type": stype, "source_id": ev["source_id"]},
                    "explanation": f"{stype} evidence freshness is within the {self._policy.max_evidence_age_days} day window.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- 3. Dataset Compatibility
        if self._policy.required_dataset_version_id:
            req_dsv = str(self._policy.required_dataset_version_id)
            actual_dsv = eval_ev["summary"].get("dataset_version_id") if eval_ev and eval_ev.get("summary") else None
            if actual_dsv == req_dsv:
                checks.append({
                    "rule_name": "dataset_version_compatibility",
                    "status": "PASS",
                    "actual_value": actual_dsv,
                    "expected_value": req_dsv,
                    "evidence_reference": {"source_type": "EVALUATION", "source_id": eval_ev["source_id"]} if eval_ev else None,
                    "explanation": f"Evaluation was executed against the required dataset version {req_dsv}.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "dataset_version_compatibility",
                    "status": "FAIL",
                    "actual_value": actual_dsv,
                    "expected_value": req_dsv,
                    "evidence_reference": {"source_type": "EVALUATION", "source_id": eval_ev["source_id"]} if eval_ev else None,
                    "explanation": f"Evaluation was executed against dataset version {actual_dsv}, but policy requires {req_dsv}.",
                    "is_blocking": True,
                })

        # ------------------------------------------------------------- 4. Reliability Score Threshold
        if self._policy.min_reliability_score is not None:
            actual_score = bench_ev["summary"].get("reliability_score") if bench_ev and bench_ev.get("summary") else None
            if actual_score is None:
                checks.append({
                    "rule_name": "min_reliability_score",
                    "status": "MISSING",
                    "actual_value": None,
                    "expected_value": f">= {self._policy.min_reliability_score}",
                    "evidence_reference": None,
                    "explanation": "No benchmark reliability score available to evaluate against threshold.",
                    "is_blocking": True,
                })
            elif actual_score >= self._policy.min_reliability_score:
                checks.append({
                    "rule_name": "min_reliability_score",
                    "status": "PASS",
                    "actual_value": actual_score,
                    "expected_value": f">= {self._policy.min_reliability_score}",
                    "evidence_reference": {"source_type": "BENCHMARK", "source_id": bench_ev["source_id"]},
                    "explanation": f"Model reliability score {actual_score:.1f} meets or exceeds required threshold of {self._policy.min_reliability_score:.1f}.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "min_reliability_score",
                    "status": "FAIL",
                    "actual_value": actual_score,
                    "expected_value": f">= {self._policy.min_reliability_score}",
                    "evidence_reference": {"source_type": "BENCHMARK", "source_id": bench_ev["source_id"]},
                    "explanation": f"Model reliability score {actual_score:.1f} is below the required threshold of {self._policy.min_reliability_score:.1f}.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- 5. Regression Severity
        if self._policy.max_regression_severity is not None:
            allowed_sev = self._policy.max_regression_severity.upper()
            sev_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            allowed_val = sev_rank.get(allowed_sev, 1)

            actual_sev = "NONE"
            if exp_ev and exp_ev.get("summary"):
                actual_sev = exp_ev["summary"].get("max_regression_severity", "NONE").upper()
            actual_val = sev_rank.get(actual_sev, 0)

            if actual_val <= allowed_val:
                checks.append({
                    "rule_name": "max_regression_severity",
                    "status": "PASS",
                    "actual_value": actual_sev,
                    "expected_value": f"<= {allowed_sev}",
                    "evidence_reference": {"source_type": "EXPERIMENT", "source_id": exp_ev["source_id"]} if exp_ev else None,
                    "explanation": f"Detected regression severity {actual_sev} is within permissible policy threshold {allowed_sev}.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "max_regression_severity",
                    "status": "FAIL",
                    "actual_value": actual_sev,
                    "expected_value": f"<= {allowed_sev}",
                    "evidence_reference": {"source_type": "EXPERIMENT", "source_id": exp_ev["source_id"]} if exp_ev else None,
                    "explanation": f"Detected regression severity {actual_sev} exceeds permissible policy limit {allowed_sev}.",
                    "is_blocking": True,
                })

        # ------------------------------------------------------------- 6. Quality Gates
        if self._policy.required_quality_gates:
            qg_passed = exp_ev["summary"].get("quality_gates_passed", True) if exp_ev and exp_ev.get("summary") else None
            if qg_passed is None:
                checks.append({
                    "rule_name": "required_quality_gates",
                    "status": "MISSING",
                    "actual_value": None,
                    "expected_value": "All quality gates pass",
                    "evidence_reference": None,
                    "explanation": "No quality gate execution evidence found.",
                    "is_blocking": True,
                })
            elif qg_passed:
                checks.append({
                    "rule_name": "required_quality_gates",
                    "status": "PASS",
                    "actual_value": "All Passed",
                    "expected_value": "All quality gates pass",
                    "evidence_reference": {"source_type": "EXPERIMENT", "source_id": exp_ev["source_id"]},
                    "explanation": "All experiment quality gates passed successfully.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "required_quality_gates",
                    "status": "FAIL",
                    "actual_value": "Failed",
                    "expected_value": "All quality gates pass",
                    "evidence_reference": {"source_type": "EXPERIMENT", "source_id": exp_ev["source_id"]},
                    "explanation": "One or more quality gates failed in experiment evaluation.",
                    "is_blocking": True,
                })

        # ------------------------------------------------------------- 7. Critical Alerts (Default 0)
        actual_crit_alerts = alert_ev["summary"].get("critical_alerts_count", 0) if alert_ev and alert_ev.get("summary") else 0
        if actual_crit_alerts <= self._policy.max_critical_alerts:
            checks.append({
                "rule_name": "critical_alerts",
                "status": "PASS",
                "actual_value": actual_crit_alerts,
                "expected_value": f"<= {self._policy.max_critical_alerts}",
                "evidence_reference": {"source_type": "ALERT", "source_id": alert_ev["source_id"]} if alert_ev else None,
                "explanation": f"Active critical alerts count ({actual_crit_alerts}) is within acceptable limit of {self._policy.max_critical_alerts}.",
                "is_blocking": False,
            })
        else:
            checks.append({
                "rule_name": "critical_alerts",
                "status": "FAIL",
                "actual_value": actual_crit_alerts,
                "expected_value": f"<= {self._policy.max_critical_alerts}",
                "evidence_reference": {"source_type": "ALERT", "source_id": alert_ev["source_id"]} if alert_ev else None,
                "explanation": f"Environment has {actual_crit_alerts} active critical alert(s), exceeding policy limit of {self._policy.max_critical_alerts}.",
                "is_blocking": True,
            })

        # ------------------------------------------------------------- 8. Error Rate Threshold
        if self._policy.max_error_rate is not None:
            actual_err = obs_ev["summary"].get("error_rate") if obs_ev and obs_ev.get("summary") else None
            if actual_err is None:
                checks.append({
                    "rule_name": "max_error_rate",
                    "status": "WARNING",
                    "actual_value": None,
                    "expected_value": f"<= {self._policy.max_error_rate * 100:.1f}%",
                    "evidence_reference": None,
                    "explanation": "No production observability error rate data available for this window.",
                    "is_blocking": False,
                })
            elif actual_err <= self._policy.max_error_rate:
                checks.append({
                    "rule_name": "max_error_rate",
                    "status": "PASS",
                    "actual_value": f"{actual_err * 100:.2f}%",
                    "expected_value": f"<= {self._policy.max_error_rate * 100:.1f}%",
                    "evidence_reference": {"source_type": "OBSERVABILITY", "source_id": obs_ev["source_id"]},
                    "explanation": f"Observed error rate {actual_err * 100:.2f}% is within the policy threshold.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "max_error_rate",
                    "status": "FAIL",
                    "actual_value": f"{actual_err * 100:.2f}%",
                    "expected_value": f"<= {self._policy.max_error_rate * 100:.1f}%",
                    "evidence_reference": {"source_type": "OBSERVABILITY", "source_id": obs_ev["source_id"]},
                    "explanation": f"Observed error rate {actual_err * 100:.2f}% exceeds permissible maximum of {self._policy.max_error_rate * 100:.1f}%.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- 9. Latency & P95
        if self._policy.max_p95_latency_ms is not None:
            actual_p95 = obs_ev["summary"].get("p95_latency_ms") if obs_ev and obs_ev.get("summary") else None
            if actual_p95 is None:
                checks.append({
                    "rule_name": "max_p95_latency",
                    "status": "WARNING",
                    "actual_value": None,
                    "expected_value": f"<= {self._policy.max_p95_latency_ms}ms",
                    "evidence_reference": None,
                    "explanation": "No P95 latency telemetry recorded for this environment.",
                    "is_blocking": False,
                })
            elif actual_p95 <= self._policy.max_p95_latency_ms:
                checks.append({
                    "rule_name": "max_p95_latency",
                    "status": "PASS",
                    "actual_value": f"{actual_p95:.1f}ms",
                    "expected_value": f"<= {self._policy.max_p95_latency_ms}ms",
                    "evidence_reference": {"source_type": "OBSERVABILITY", "source_id": obs_ev["source_id"]},
                    "explanation": f"P95 latency {actual_p95:.1f}ms is within policy threshold of {self._policy.max_p95_latency_ms}ms.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "max_p95_latency",
                    "status": "FAIL",
                    "actual_value": f"{actual_p95:.1f}ms",
                    "expected_value": f"<= {self._policy.max_p95_latency_ms}ms",
                    "evidence_reference": {"source_type": "OBSERVABILITY", "source_id": obs_ev["source_id"]},
                    "explanation": f"P95 latency {actual_p95:.1f}ms exceeds policy limit of {self._policy.max_p95_latency_ms}ms.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- 10. Sample Size & Statistical Confidence
        if self._policy.min_sample_size is not None:
            bench_n = bench_ev["summary"].get("sample_size", 0) if bench_ev and bench_ev.get("summary") else 0
            eval_n = eval_ev["summary"].get("total_tests", 0) if eval_ev and eval_ev.get("summary") else 0
            sample_n = max(bench_n, eval_n)

            if sample_n >= self._policy.min_sample_size:
                checks.append({
                    "rule_name": "min_sample_size",
                    "status": "PASS",
                    "actual_value": sample_n,
                    "expected_value": f">= {self._policy.min_sample_size}",
                    "evidence_reference": {"source_type": "BENCHMARK" if bench_n >= eval_n else "EVALUATION"},
                    "explanation": f"Evaluation sample size of {sample_n} satisfies policy minimum of {self._policy.min_sample_size}.",
                    "is_blocking": False,
                })
            elif sample_n >= int(self._policy.min_sample_size * 0.8):
                checks.append({
                    "rule_name": "min_sample_size",
                    "status": "WARNING",
                    "actual_value": sample_n,
                    "expected_value": f">= {self._policy.min_sample_size}",
                    "evidence_reference": {"source_type": "BENCHMARK" if bench_n >= eval_n else "EVALUATION"},
                    "explanation": f"Sample size {sample_n} is close to policy minimum of {self._policy.min_sample_size}.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "min_sample_size",
                    "status": "MISSING" if sample_n == 0 else "FAIL",
                    "actual_value": sample_n,
                    "expected_value": f">= {self._policy.min_sample_size}",
                    "evidence_reference": {"source_type": "BENCHMARK" if bench_n >= eval_n else "EVALUATION"},
                    "explanation": f"Sample size {sample_n} is insufficient (minimum required is {self._policy.min_sample_size}).",
                    "is_blocking": False,
                })

        if self._policy.min_statistical_confidence is not None:
            actual_conf = bench_ev["summary"].get("statistical_confidence") if bench_ev and bench_ev.get("summary") else None
            if actual_conf is None:
                checks.append({
                    "rule_name": "min_statistical_confidence",
                    "status": "WARNING",
                    "actual_value": None,
                    "expected_value": f">= {self._policy.min_statistical_confidence:.2f}",
                    "evidence_reference": None,
                    "explanation": "No statistical confidence level calculated for current benchmarks.",
                    "is_blocking": False,
                })
            elif actual_conf >= self._policy.min_statistical_confidence:
                checks.append({
                    "rule_name": "min_statistical_confidence",
                    "status": "PASS",
                    "actual_value": round(actual_conf, 3),
                    "expected_value": f">= {self._policy.min_statistical_confidence:.2f}",
                    "evidence_reference": {"source_type": "BENCHMARK", "source_id": bench_ev["source_id"]},
                    "explanation": f"Statistical confidence {actual_conf:.3f} meets policy requirement of {self._policy.min_statistical_confidence:.2f}.",
                    "is_blocking": False,
                })
            else:
                checks.append({
                    "rule_name": "min_statistical_confidence",
                    "status": "FAIL",
                    "actual_value": round(actual_conf, 3),
                    "expected_value": f">= {self._policy.min_statistical_confidence:.2f}",
                    "evidence_reference": {"source_type": "BENCHMARK", "source_id": bench_ev["source_id"]},
                    "explanation": f"Statistical confidence {actual_conf:.3f} is below policy requirement of {self._policy.min_statistical_confidence:.2f}.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- 11. Agent Evaluation & Safety (Phase 11)
        if agent_ev and agent_ev.get("summary"):
            agent_safety = agent_ev["summary"].get("safety_violations", 0)
            if agent_safety > 0:
                checks.append({
                    "rule_name": "agent_safety_violations",
                    "status": "FAIL",
                    "actual_value": agent_safety,
                    "expected_value": 0,
                    "evidence_reference": {"source_type": "AGENT_EVALUATION", "source_id": agent_ev["source_id"]},
                    "explanation": f"CRITICAL SAFETY VIOLATION: Agent committed {agent_safety} safety violation(s) during task trajectory.",
                    "is_blocking": True,
                })
            else:
                checks.append({
                    "rule_name": "agent_safety_violations",
                    "status": "PASS",
                    "actual_value": 0,
                    "expected_value": 0,
                    "evidence_reference": {"source_type": "AGENT_EVALUATION", "source_id": agent_ev["source_id"]},
                    "explanation": "No agent trajectory safety violations detected.",
                    "is_blocking": True,
                })

        # ------------------------------------------------------------- 14. Agent Reliability & Safety
        if agent_ev and agent_ev.get("summary"):
            safety_passed = agent_ev["summary"].get("safety_passed", True)
            safety_violations = agent_ev["summary"].get("safety_violations", 0)
            if not safety_passed or safety_violations > 0:
                checks.append({
                    "rule_name": "agent_safety",
                    "status": "FAIL",
                    "actual_value": f"{safety_violations} safety violations",
                    "expected_value": "0 safety violations",
                    "evidence_reference": {"source_type": agent_ev["source_type"], "source_id": agent_ev["source_id"]},
                    "explanation": f"Agent reliability evidence has {safety_violations} safety violations.",
                    "is_blocking": True,
                })
            else:
                checks.append({
                    "rule_name": "agent_safety",
                    "status": "PASS",
                    "actual_value": "0 safety violations",
                    "expected_value": "0 safety violations",
                    "evidence_reference": {"source_type": agent_ev["source_type"], "source_id": agent_ev["source_id"]},
                    "explanation": "Agent reliability safety criteria met.",
                    "is_blocking": False,
                })

        # ------------------------------------------------------------- Compute Readiness Score (0..100)
        readiness_score, breakdown = self._compute_readiness_score(eval_ev, exp_ev, bench_ev, obs_ev, alert_ev, agent_ev)

        # ------------------------------------------------------------- Determine Outcome
        # Core Feature 7 Rule: Blocking policy rules ALWAYS win, regardless of readiness score.
        blocking_checks = [c for c in checks if c["is_blocking"] and c["status"] in ("FAIL", "MISSING")]
        missing_required = [c for c in checks if c["status"] == "MISSING"]
        failing_checks = [c for c in checks if c["status"] == "FAIL"]
        warning_checks = [c for c in checks if c["status"] == "WARNING"]
        stale_checks = [c for c in checks if c["status"] == "STALE"]

        if blocking_checks:
            outcome = "BLOCKED"
        elif missing_required and (self._policy.required_benchmark or self._policy.required_evaluation):
            outcome = "INSUFFICIENT_EVIDENCE"
        elif failing_checks:
            outcome = "REJECTED"
        elif warning_checks or stale_checks:
            outcome = "CONDITIONALLY_APPROVED"
        else:
            outcome = "APPROVED"

        # Generate recommendations
        recommendations = self._generate_recommendations(outcome, checks, eval_ev, exp_ev, bench_ev, obs_ev, alert_ev)

        return {
            "outcome": outcome,
            "readiness_score": readiness_score,
            "readiness_breakdown": breakdown,
            "checks": checks,
            "recommendations": recommendations,
        }

    def _compute_readiness_score(
        self,
        eval_ev: dict | None,
        exp_ev: dict | None,
        bench_ev: dict | None,
        obs_ev: dict | None,
        alert_ev: dict | None,
        agent_ev: dict | None = None,
    ) -> tuple[float, dict[str, Any]]:
        """Calculate a 0–100 score across 6 or 7 weighted dimensions (Phase 15)."""
        breakdown: dict[str, Any] = {}
        has_agent = bool(agent_ev and agent_ev.get("summary"))

        w_eval = 0.15 if has_agent else 0.20
        w_bench = 0.20 if has_agent else 0.25
        w_reg = 0.15 if has_agent else 0.20
        w_agent = 0.15 if has_agent else 0.0

        # 1. Evaluation Quality
        eval_acc = eval_ev["summary"].get("accuracy_score", 0.0) if eval_ev and eval_ev.get("summary") else 50.0
        breakdown["evaluation_quality"] = {"score": eval_acc, "weight": w_eval}

        # 2. Benchmark Reliability
        bench_rel = bench_ev["summary"].get("reliability_score", 0.0) if bench_ev and bench_ev.get("summary") else 50.0
        breakdown["benchmark_reliability"] = {"score": bench_rel, "weight": w_bench}

        # 3. Regression Safety
        reg_sev = exp_ev["summary"].get("max_regression_severity", "NONE").upper() if exp_ev and exp_ev.get("summary") else "NONE"
        reg_score_map = {"NONE": 100.0, "LOW": 85.0, "MEDIUM": 60.0, "HIGH": 20.0, "CRITICAL": 0.0}
        reg_score = reg_score_map.get(reg_sev, 80.0)
        breakdown["regression_safety"] = {"score": reg_score, "weight": w_reg}

        # 4. Agent Reliability (when present)
        if has_agent:
            agent_score = agent_ev["summary"].get("reliability_score", 0.0)
            breakdown["agent_reliability"] = {"score": agent_score, "weight": w_agent}

        # 5. Production Stability (weight 15%)
        obs_avail = obs_ev["summary"].get("availability", 0.99) * 100.0 if obs_ev and obs_ev.get("summary") else 95.0
        breakdown["production_stability"] = {"score": min(100.0, max(0.0, obs_avail)), "weight": 0.15}

        # 6. Alert Health (weight 10%)
        crit_alerts = alert_ev["summary"].get("critical_alerts_count", 0) if alert_ev and alert_ev.get("summary") else 0
        total_alerts = alert_ev["summary"].get("total_active_alerts", 0) if alert_ev and alert_ev.get("summary") else 0
        if crit_alerts > 0:
            alert_score = 0.0
        elif total_alerts > 0:
            alert_score = 60.0
        else:
            alert_score = 100.0
        breakdown["alert_health"] = {"score": alert_score, "weight": 0.10}

        # 7. Efficiency / Latency (weight 10%)
        p95 = obs_ev["summary"].get("p95_latency_ms", 1000.0) if obs_ev and obs_ev.get("summary") else 1000.0
        eff_score = max(0.0, min(100.0, 100.0 - (p95 / 50.0)))
        breakdown["efficiency"] = {"score": round(eff_score, 1), "weight": 0.10}

        total_score = sum(item["score"] * item["weight"] for item in breakdown.values())
        return round(total_score, 1), breakdown

    def _generate_recommendations(
        self,
        outcome: str,
        checks: list[dict[str, Any]],
        eval_ev: dict | None,
        exp_ev: dict | None,
        bench_ev: dict | None,
        obs_ev: dict | None,
        alert_ev: dict | None,
    ) -> list[dict[str, Any]]:
        """Generate deterministic, evidence-backed recommendations distinguishing facts from suggestions."""
        recs: list[dict[str, Any]] = []

        if outcome == "BLOCKED":
            crit = alert_ev["summary"].get("critical_alerts_count", 0) if alert_ev and alert_ev.get("summary") else 0
            if crit > 0:
                recs.append({
                    "type": "BLOCK_ACTION",
                    "fact": f"{crit} critical production alert(s) currently triggered in environment.",
                    "suggestion": "Acknowledge and remediate active critical alerts before proceeding with deployment.",
                })
            reg_sev = exp_ev["summary"].get("max_regression_severity", "NONE") if exp_ev and exp_ev.get("summary") else "NONE"
            if reg_sev in ("HIGH", "CRITICAL"):
                recs.append({
                    "type": "BLOCK_ACTION",
                    "fact": f"Regression severity {reg_sev} detected in model candidate comparison.",
                    "suggestion": "Investigate regression failure clusters in experiment results and adjust model configuration or prompts.",
                })

        elif outcome == "INSUFFICIENT_EVIDENCE":
            if not bench_ev:
                recs.append({
                    "type": "EVIDENCE_COLLECTION",
                    "fact": "No benchmark execution found for candidate model.",
                    "suggestion": "Execute the benchmark suite against candidate to calculate empirical reliability and Welch's t-test confidence.",
                })
            if not eval_ev:
                recs.append({
                    "type": "EVIDENCE_COLLECTION",
                    "fact": "No evaluation run recorded for candidate model.",
                    "suggestion": "Trigger an evaluation run across test dataset to verify rubric accuracy.",
                })

        elif outcome == "REJECTED":
            rel = bench_ev["summary"].get("reliability_score", 0.0) if bench_ev and bench_ev.get("summary") else 0.0
            recs.append({
                "type": "QUALITY_IMPROVEMENT",
                "fact": f"Reliability score ({rel:.1f}) is below policy threshold ({self._policy.min_reliability_score}).",
                "suggestion": "Tune model hyperparameters, prompt templates, or temperature to improve reliability.",
            })

        elif outcome == "CONDITIONALLY_APPROVED":
            sample_warning = any(c["rule_name"] == "min_sample_size" and c["status"] == "WARNING" for c in checks)
            if sample_warning:
                recs.append({
                    "type": "COVERAGE_WARNING",
                    "fact": "Evaluation sample size is close to the policy minimum threshold.",
                    "suggestion": "Increase evaluation dataset sample size before broad rollout to improve statistical certainty.",
                })
            stale_warning = any(c["status"] == "STALE" for c in checks)
            if stale_warning:
                recs.append({
                    "type": "FRESHNESS_WARNING",
                    "fact": "One or more evidence sources have aged past policy threshold.",
                    "suggestion": "Trigger a fresh benchmark run to update confidence metrics.",
                })

        elif outcome == "APPROVED":
            recs.append({
                "type": "PROCEED",
                "fact": "All policy rules, quality gates, reliability thresholds, and alert health checks passed cleanly.",
                "suggestion": "Model is safe, stable, and ready for deployment to the target environment.",
            })

        return recs
