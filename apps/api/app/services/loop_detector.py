"""Deterministic and explainable loop detection algorithm for Agent Trajectories (Core Feature 10)."""

from __future__ import annotations

import json
from typing import Any


class LoopDetector:
    """Detects repeated identical tool calls, cyclic sequences, and non-progressing loops."""

    @staticmethod
    def _canonical_args(args: Any) -> str:
        if isinstance(args, dict):
            return json.dumps(args, sort_keys=True)
        return str(args or "")

    def detect(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze trajectory steps for loops.
        
        Returns:
            dict containing:
                - is_loop_detected (bool)
                - loop_count (int)
                - loop_type (str | None): REPEATED_IDENTICAL_TOOL, CYCLIC_TOOL_SEQUENCE, REPEATED_STATE
                - explanation (str)
                - step_references (list[int])
        """
        tool_steps = [
            (s.get("step_number", idx + 1), s.get("tool_name", ""), self._canonical_args(s.get("tool_arguments")))
            for idx, s in enumerate(steps)
            if s.get("step_type") == "TOOL_CALL" and s.get("tool_name")
        ]

        if len(tool_steps) < 3:
            return {
                "is_loop_detected": False,
                "loop_count": 0,
                "loop_type": None,
                "explanation": "Trajectory too short to constitute a loop.",
                "step_references": [],
            }

        # 1. Check for repeated identical tool calls (>= 3 consecutive identical tool + args)
        consecutive_identical = 1
        last_item = None
        loop_refs: list[int] = []

        for step_no, tool_name, args_str in tool_steps:
            current = (tool_name, args_str)
            if current == last_item:
                consecutive_identical += 1
                loop_refs.append(step_no)
                if consecutive_identical >= 3:
                    return {
                        "is_loop_detected": True,
                        "loop_count": consecutive_identical,
                        "loop_type": "REPEATED_IDENTICAL_TOOL",
                        "explanation": (
                            f"Identical tool call '{tool_name}' repeated {consecutive_identical} times "
                            f"with arguments {args_str} without meaningful state change."
                        ),
                        "step_references": loop_refs,
                    }
            else:
                consecutive_identical = 1
                last_item = current
                loop_refs = [step_no]

        # 2. Check for cyclic tool sequence loops (e.g., A -> B -> A -> B -> A -> B)
        # Sequence of length 2 repeated 3 times = 6 calls
        # Sequence of length 3 repeated 2 times = 6 calls
        tool_names = [t[1] for t in tool_steps]
        n = len(tool_names)

        for cycle_len in (2, 3):
            if n >= cycle_len * 2:
                for start_idx in range(n - cycle_len * 2 + 1):
                    pattern = tool_names[start_idx : start_idx + cycle_len]
                    repeats = 0
                    curr = start_idx
                    while curr + cycle_len <= n and tool_names[curr : curr + cycle_len] == pattern:
                        repeats += 1
                        curr += cycle_len

                    if repeats >= 3 or (cycle_len >= 2 and repeats >= 2 and n <= 8):
                        affected_steps = [tool_steps[i][0] for i in range(start_idx, curr)]
                        pattern_str = " -> ".join(pattern)
                        return {
                            "is_loop_detected": True,
                            "loop_count": repeats,
                            "loop_type": "CYCLIC_TOOL_SEQUENCE",
                            "explanation": f"Cyclic tool call sequence '{pattern_str}' repeated {repeats} times in trajectory.",
                            "step_references": affected_steps,
                        }

        return {
            "is_loop_detected": False,
            "loop_count": 0,
            "loop_type": None,
            "explanation": "No non-progressing loops detected.",
            "step_references": [],
        }
