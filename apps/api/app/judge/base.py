"""LLM judge abstraction (Phase 4 §6–§13, §17, §36).

The judge is provider-independent: it only knows about rubrics and normalized
scores. Judge models are always invoked through the Model Gateway
(see :mod:`app.judge.llm_judge`), never through provider SDKs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class JudgeError(Exception):
    """Base error for judge failures (mapped to an ERROR result)."""


@dataclass
class JudgeCriterion:
    name: str
    description: str
    weight: float
    min_score: float = 0.0
    max_score: float = 1.0


@dataclass
class JudgeRubric:
    name: str
    description: str | None
    version: int
    criteria: list[JudgeCriterion]

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> JudgeRubric:
        """Rebuild a rubric from its frozen run snapshot (reproducibility)."""
        return cls(
            name=str(snapshot.get("name") or "Rubric"),
            description=snapshot.get("description"),
            version=int(snapshot.get("version") or 1),
            criteria=[
                JudgeCriterion(
                    name=str(c["name"]),
                    description=str(c.get("description") or ""),
                    weight=float(c.get("weight", 0.0)),
                    min_score=float(c.get("min_score", 0.0)),
                    max_score=float(c.get("max_score", 1.0)),
                )
                for c in snapshot.get("criteria") or []
            ],
        )


@dataclass
class JudgeResult:
    """Normalized judge result (Phase 4 §11, §13)."""

    score: float
    passed: bool
    confidence: float
    reasoning: str
    criteria: dict[str, float]
    judge_model: str
    judge_model_version: str
    judge_prompt_version: str
    rubric_version: int
    usage: Any | None = None


class LLMJudge(Protocol):
    """Provider-independent judge interface (Phase 4 §7)."""

    async def evaluate(
        self,
        *,
        input_text: str,
        expected_output: str | None,
        actual_output: str,
        rubric: JudgeRubric,
        context: str | None = None,
    ) -> JudgeResult: ...
