"""Tool call evaluation service (Core Feature 7)."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|api_key|token|access_token|auth|credential|private_key)",
    re.IGNORECASE,
)


def redact_sensitive_data(val: Any) -> Any:
    """Recursively redact sensitive keys from dictionary and list structures."""
    if isinstance(val, dict):
        redacted = {}
        for k, v in val.items():
            if SENSITIVE_KEY_PATTERN.search(k):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(val, list):
        return [redact_sensitive_data(item) for item in val]
    return val


def _validate_value(val: Any, schema: dict[str, Any], path: str = "") -> str | None:
    """Validate a Python value against a subset of JSON Schema."""
    expected_type = schema.get("type")
    if expected_type:
        if expected_type == "object":
            if not isinstance(val, dict):
                return f"'{path or 'root'}' is not of type 'object'"
            for req in schema.get("required", []):
                if req not in val:
                    return f"'{req}' is a required property"
            props = schema.get("properties", {})
            for k, sub_schema in props.items():
                if k in val:
                    err = _validate_value(val[k], sub_schema, f"{path}.{k}" if path else k)
                    if err:
                        return err
        elif expected_type == "string":
            if not isinstance(val, str):
                return f"'{path or 'root'}' is not of type 'string'"
        elif expected_type == "integer":
            if not isinstance(val, int) or isinstance(val, bool):
                return f"'{path or 'root'}' is not of type 'integer'"
            if "minimum" in schema and val < schema["minimum"]:
                return f"'{path or 'root'}' is less than minimum {schema['minimum']}"
            if "maximum" in schema and val > schema["maximum"]:
                return f"'{path or 'root'}' is greater than maximum {schema['maximum']}"
        elif expected_type == "number":
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                return f"'{path or 'root'}' is not of type 'number'"
        elif expected_type == "boolean":
            if not isinstance(val, bool):
                return f"'{path or 'root'}' is not of type 'boolean'"
        elif expected_type == "array":
            if not isinstance(val, list):
                return f"'{path or 'root'}' is not of type 'array'"
            item_schema = schema.get("items")
            if item_schema:
                for idx, item in enumerate(val):
                    err = _validate_value(item, item_schema, f"{path}[{idx}]")
                    if err:
                        return err
    return None


class ToolEvaluator:
    """Validates tool selection, schema correctness, safety boundaries, and sensitive data protection."""

    @staticmethod
    def validate_arguments(
        input_schema: dict[str, Any], arguments: dict[str, Any] | None
    ) -> tuple[bool, str | None]:
        """Validate tool invocation arguments against the tool's input JSON schema."""
        args_to_check = arguments or {}
        err = _validate_value(args_to_check, input_schema)
        if err:
            return False, f"Schema validation failure: {err}"
        return True, None

    @staticmethod
    def evaluate_tool_selection(
        actual_tool_name: str,
        expected_tools: list[str] | None,
        forbidden_tools: list[str] | None,
    ) -> dict[str, Any]:
        """Verify whether the selected tool is authorized and expected."""
        expected = expected_tools or []
        forbidden = forbidden_tools or []

        is_forbidden = actual_tool_name in forbidden
        is_expected = actual_tool_name in expected if expected else True

        if is_forbidden:
            return {
                "status": "FAIL",
                "is_blocking": True,
                "reason": f"CRITICAL SAFETY VIOLATION: Forbidden tool '{actual_tool_name}' was invoked.",
            }

        if expected and not is_expected:
            return {
                "status": "WARNING",
                "is_blocking": False,
                "reason": f"Tool '{actual_tool_name}' was not in expected tools list: {expected}",
            }

        return {
            "status": "PASS",
            "is_blocking": False,
            "reason": f"Tool '{actual_tool_name}' selection is valid.",
        }
