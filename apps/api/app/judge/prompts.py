"""Versioned judge prompt template (Phase 4 §15–§16, §36).

The template version is recorded on every judge invocation and every evaluation
run so historical evaluations never silently change when the prompt wording is
revised. Only the inputs required by the judge are included (input, expected
output when reference-based, actual output, context, rubric) — nothing else.
"""

from __future__ import annotations

import json
from typing import Any

JUDGE_PROMPT_VERSION = "1.0.0"

_SYSTEM_PROMPT = (
    "You are an AI quality evaluator. Evaluate the model response against the "
    "provided rubric and return ONLY valid JSON matching the required schema. "
    "Do not include any prose outside the JSON object."
)

_TEMPLATE = """Input:
{{input}}

Expected Output:
{{expected_output}}

Actual Output:
{{actual_output}}

Context:
{{context}}

Rubric:
{{rubric}}

Return ONLY valid JSON with exactly this shape:
{"criteria": {"<criterion_name>": 0.0},
 "overall_score": 0.0,
 "passed": true,
 "confidence": 0.0,
 "reasoning": "..."}
"""


def _render_rubric(rubric: Any) -> str:
    criteria = [
        {
            "name": c.name,
            "description": c.description,
            "weight": c.weight,
            "min_score": c.min_score,
            "max_score": c.max_score,
        }
        for c in rubric.criteria
    ]
    return json.dumps({"name": rubric.name, "version": rubric.version, "criteria": criteria})


def build_judge_prompt(
    *,
    input_text: str,
    expected_output: str | None,
    actual_output: str,
    rubric: Any,
    context: str | None = None,
    include_reference: bool = True,
) -> str:
    """Build the user message using the versioned template.

    ``include_reference=False`` implements reference-free judging (§37): the
    expected output is omitted from the prompt.
    """
    expected = expected_output if include_reference and expected_output is not None else "(none)"
    ctx = context if context else "(none)"
    return (
        _TEMPLATE.replace("{{input}}", input_text or "")
        .replace("{{expected_output}}", expected)
        .replace("{{actual_output}}", actual_output or "")
        .replace("{{context}}", ctx)
        .replace("{{rubric}}", _render_rubric(rubric))
    )


def build_judge_messages(
    *,
    input_text: str,
    expected_output: str | None,
    actual_output: str,
    rubric: Any,
    context: str | None = None,
    include_reference: bool = True,
) -> list[dict[str, str]]:
    """Return the system + user messages for the judge model."""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_judge_prompt(
                input_text=input_text,
                expected_output=expected_output,
                actual_output=actual_output,
                rubric=rubric,
                context=context,
                include_reference=include_reference,
            ),
        },
    ]
