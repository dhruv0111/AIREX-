"""Organization-scoped judge result cache (Phase 4 §34–§35, §38).

The cache key is a SHA-256 over the full judge context (target output, input,
expected output, context, rubric version, judge model, prompt version) so it
never depends on a test-case id alone and never leaks across organizations.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from app.core.metrics import llm_judge_cache_hits_total


class JudgeCache:
    """In-memory, organization-scoped cache of normalized judge responses."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    @staticmethod
    def make_key(
        *,
        target_output: str,
        input_text: str,
        expected_output: str | None,
        context: str | None,
        rubric_version: int,
        judge_model: str,
        judge_prompt_version: str,
    ) -> str:
        payload = json.dumps(
            {
                "target_output": target_output,
                "input": input_text,
                "expected": expected_output,
                "context": context,
                "rubric_version": rubric_version,
                "judge_model": judge_model,
                "prompt_version": judge_prompt_version,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def get(self, organization_id: UUID, key: str) -> dict[str, Any] | None:
        org = self._store.get(str(organization_id))
        if org is None:
            return None
        value = org.get(key)
        if value is not None:
            llm_judge_cache_hits_total.inc()
        return value

    async def put(self, organization_id: UUID, key: str, value: dict[str, Any]) -> None:
        self._store.setdefault(str(organization_id), {})[key] = value

    def clear(self) -> None:
        self._store.clear()
