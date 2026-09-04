"""Agent Reliability Scoring Engine (Core Feature 9)."""

from __future__ import annotations

from typing import Any

METHODOLOGY_VERSION = "1.0.0"


class AgentReliabilityScorer:
    """Computes deterministic, multi-dimensional Agent Reliability Score (0–100)."""

    WEIGHTS = {
        "goal_completion": 0.35,
        "tool_correctness": 0.25,
        "trajectory_efficiency": 0.15,
        "failure_recovery": 0.15,
        "output_quality": 0.10,
    }

    def compute_score(
        self,
        *,
        goal_status: str,
        evaluation_results: dict[str, Any],
        max_steps: int = 15,
        max_tool_calls: int = 25,
    ) -> tuple[float, dict[str, Any], str]:
        """Calculate aggregate reliability score and dimension breakdown.
        
        Returns:
            (score, breakdown, safety_status)
            where safety_status is 'PASS' or 'BLOCKED'.
        """
        metrics = evaluation_results.get("metrics", {})
        safety_violations = metrics.get("safety_violations", 0)
        is_blocked = (
            safety_violations > 0
            or evaluation_results.get("overall_status") == "BLOCKED"
        )
        safety_status = "BLOCKED" if is_blocked else "PASS"

        # 1. Goal Completion Score (0-100)
        if goal_status == "COMPLETED":
            goal_score = 100.0
        elif goal_status == "PARTIAL":
            goal_score = 50.0
        else:
            goal_score = 0.0

        # 2. Tool Correctness Score (0-100)
        total_calls = metrics.get("total_tool_calls", 0)
        failed_calls = metrics.get("failed_tool_calls", 0)
        if total_calls > 0:
            tool_score = max(0.0, 100.0 * (1.0 - (failed_calls / total_calls)))
        else:
            tool_score = 100.0

        # 3. Trajectory Efficiency Score (0-100)
        total_steps = metrics.get("total_steps", 0)
        loops_detected = metrics.get("loops_detected", 0)
        step_penalty = max(0.0, (total_steps - max_steps) * 5.0) if total_steps > max_steps else 0.0
        loop_penalty = 30.0 if loops_detected > 0 else 0.0
        efficiency_score = max(0.0, 100.0 - step_penalty - loop_penalty)

        # 4. Failure Recovery Score (0-100)
        recovery_rate = metrics.get("recovery_rate", 1.0)
        recovery_score = recovery_rate * 100.0

        # 5. Output Quality Score (0-100)
        output_quality_score = 100.0 if goal_status == "COMPLETED" else 20.0

        # Weighted aggregate
        aggregate_score = (
            goal_score * self.WEIGHTS["goal_completion"]
            + tool_score * self.WEIGHTS["tool_correctness"]
            + efficiency_score * self.WEIGHTS["trajectory_efficiency"]
            + recovery_score * self.WEIGHTS["failure_recovery"]
            + output_quality_score * self.WEIGHTS["output_quality"]
        )

        final_score = round(max(0.0, min(100.0, aggregate_score)), 2)

        breakdown = {
            "methodology_version": METHODOLOGY_VERSION,
            "overall_score": final_score,
            "safety_status": safety_status,
            "dimensions": {
                "goal_completion": {"score": goal_score, "weight": self.WEIGHTS["goal_completion"]},
                "tool_correctness": {"score": tool_score, "weight": self.WEIGHTS["tool_correctness"]},
                "trajectory_efficiency": {"score": efficiency_score, "weight": self.WEIGHTS["trajectory_efficiency"]},
                "failure_recovery": {"score": recovery_score, "weight": self.WEIGHTS["failure_recovery"]},
                "output_quality": {"score": output_quality_score, "weight": self.WEIGHTS["output_quality"]},
            },
        }

        return final_score, breakdown, safety_status
