"""Versioned test-generation prompt template (Phase 5)."""

from __future__ import annotations

import json
from typing import Any

GENERATION_PROMPT_VERSION = "1.0.0"

_SYSTEM_PROMPT = (
    "You are a test-generation assistant for an AI application. "
    "Return ONLY valid JSON matching the required schema."
)

_TEMPLATE = """You are generating evaluation test cases for an AI application.

Application / instruction / use case:
{{instruction}}

Generation type: {{generation_type}}

Difficulty distribution: {{difficulty_distribution}}

Source material (may be '(none)'):
{{source_material}}

Generate {{count}} test cases. Return ONLY valid JSON with exactly this shape:
{"test_cases": [{"input": "...", "expected_output": "...", "context": "...",
"category": "...", "difficulty": "easy|medium|hard",
"generation_type": "BASIC|EDGE_CASE|BOUNDARY|NEGATIVE|AMBIGUOUS|ADVERSARIAL"}]}
"""


def build_generation_prompt(
    *,
    instruction: str | None,
    generation_type: str,
    difficulty_distribution: dict[str, float] | None,
    source_material: str | None,
    count: int,
) -> str:
    """Build the user message using the versioned template."""
    return (
        _TEMPLATE.replace("{{instruction}}", instruction or "")
        .replace("{{generation_type}}", generation_type)
        .replace("{{difficulty_distribution}}", json.dumps(difficulty_distribution or {}))
        .replace("{{source_material}}", source_material or "(none)")
        .replace("{{count}}", str(count))
    )


def build_generation_messages(
    *,
    instruction: str | None,
    generation_type: str,
    difficulty_distribution: dict[str, float] | None,
    source_material: str | None,
    count: int,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_generation_prompt(
                instruction=instruction,
                generation_type=generation_type,
                difficulty_distribution=difficulty_distribution,
                source_material=source_material,
                count=count,
            ),
        },
    ]


def render_source_material(source: list[dict[str, Any]]) -> str:
    """Render source test cases / records compactly for the prompt."""
    if not source:
        return "(none)"
    return json.dumps(source, ensure_ascii=False, default=str)[:12000]
