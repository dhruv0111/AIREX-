"""Agent execution gateway and local deterministic test agent (Core Feature 6)."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import time
from typing import Any
from uuid import UUID, uuid4

from app.models.agent import AgentDefinition


def compute_agent_fingerprint(
    *,
    agent_name: str,
    agent_type: str,
    version: int,
    system_prompt: str | None = None,
    tool_manifest: list[Any] | None = None,
    configuration: dict[str, Any] | None = None,
    model_id: UUID | None = None,
    provider_id: UUID | None = None,
) -> str:
    """Deterministic SHA-256 fingerprint representing an immutable agent configuration state."""
    payload = {
        "name": agent_name,
        "type": agent_type,
        "version": version,
        "system_prompt": system_prompt or "",
        "tool_manifest": tool_manifest or [],
        "configuration": configuration or {},
        "model_id": str(model_id) if model_id else "",
        "provider_id": str(provider_id) if provider_id else "",
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


class DeterministicLocalTestAgent:
    """Local deterministic test agent for unit and integration testing."""

    @classmethod
    def execute(
        cls,
        *,
        agent_def: AgentDefinition,
        task: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Simulate deterministic multi-step agent trajectory steps."""
        meta = task.get("metadata", {}) or {}
        instruction = task.get("instruction", "Execute task")
        steps: list[dict[str, Any]] = []
        step_no = 1

        # Step 1: Initial Model Request
        steps.append({
            "step_number": step_no,
            "step_type": "MODEL_REQUEST",
            "status": "SUCCESS",
            "model_input": instruction,
            "duration_ms": 120.0,
            "timestamp": datetime.now(UTC),
        })
        step_no += 1

        # Check for simulated behaviors
        if meta.get("simulate_loop"):
            # Repeat identical tool call 3 times to trigger loop detection
            tool_name = "search_tool"
            tool_args = {"query": "climate data"}
            for _ in range(3):
                steps.append({
                    "step_number": step_no,
                    "step_type": "TOOL_CALL",
                    "status": "SUCCESS",
                    "tool_name": tool_name,
                    "tool_call_id": f"call_{uuid4().hex[:6]}",
                    "tool_arguments": tool_args,
                    "duration_ms": 80.0,
                    "timestamp": datetime.now(UTC),
                })
                step_no += 1
                steps.append({
                    "step_number": step_no,
                    "step_type": "TOOL_RESULT",
                    "status": "SUCCESS",
                    "tool_name": tool_name,
                    "tool_result": {"results": ["Sample result"]},
                    "duration_ms": 50.0,
                    "timestamp": datetime.now(UTC),
                })
                step_no += 1

        elif meta.get("simulate_forbidden_tool"):
            forbidden = task.get("forbidden_tools", ["delete_database"])
            target = forbidden[0] if forbidden else "forbidden_tool"
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_CALL",
                "status": "SUCCESS",
                "tool_name": target,
                "tool_call_id": f"call_{uuid4().hex[:6]}",
                "tool_arguments": {"force": True},
                "duration_ms": 40.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_RESULT",
                "status": "SUCCESS",
                "tool_name": target,
                "tool_result": {"status": "executed"},
                "duration_ms": 30.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1

        elif meta.get("simulate_failure_and_recover"):
            # Step: Tool call that fails
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_CALL",
                "status": "SUCCESS",
                "tool_name": "fetch_api",
                "tool_call_id": f"call_{uuid4().hex[:6]}",
                "tool_arguments": {"endpoint": "/data"},
                "duration_ms": 90.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_RESULT",
                "status": "FAIL",
                "tool_name": "fetch_api",
                "error_category": "TIMEOUT",
                "error_message": "Network connection timed out.",
                "duration_ms": 500.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1

            # Retry step with backoff: Succeeds
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_CALL",
                "status": "SUCCESS",
                "tool_name": "fetch_api",
                "tool_call_id": f"call_{uuid4().hex[:6]}",
                "tool_arguments": {"endpoint": "/data", "retry": True},
                "duration_ms": 100.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_RESULT",
                "status": "SUCCESS",
                "tool_name": "fetch_api",
                "tool_result": {"status": "ok", "items": [1, 2, 3]},
                "duration_ms": 80.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1

        else:
            # Standard successful multi-step tool trajectory
            tools = task.get("expected_tools") or ["calculator"]
            target_tool = tools[0]
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_CALL",
                "status": "SUCCESS",
                "tool_name": target_tool,
                "tool_call_id": f"call_{uuid4().hex[:6]}",
                "tool_arguments": {"expression": "24 * 7"},
                "duration_ms": 60.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1
            steps.append({
                "step_number": step_no,
                "step_type": "TOOL_RESULT",
                "status": "SUCCESS",
                "tool_name": target_tool,
                "tool_result": {"result": 168},
                "duration_ms": 30.0,
                "timestamp": datetime.now(UTC),
            })
            step_no += 1

        # Final Step: Model Response & Output
        steps.append({
            "step_number": step_no,
            "step_type": "FINAL",
            "status": "SUCCESS",
            "model_output": "The calculation and goal have been completed successfully.",
            "duration_ms": 110.0,
            "timestamp": datetime.now(UTC),
        })

        return steps
