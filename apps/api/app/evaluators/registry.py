"""Evaluator registry (Phase 3 §22, §42; Phase 4 §24–§25).

The evaluation engine discovers evaluators through the registry by name; the
worker never contains a giant conditional over evaluator types. Each evaluator
carries a semantic version so historical runs retain the exact evaluator used.
Phase 4 adds the asynchronous ``llm_judge`` evaluator; provider-backed
evaluators receive a dependency context through ``build(name, deps)``.
"""

from __future__ import annotations

from typing import Any

from app.evaluators.base import BaseEvaluator, EvaluatorError
from app.evaluators.deterministic import (
    CaseInsensitiveExactMatchEvaluator,
    ContainsEvaluator,
    ExactMatchEvaluator,
    JsonMatchEvaluator,
    LengthEvaluator,
    NumericMatchEvaluator,
    RegexEvaluator,
    SafetyRefusalEvaluator,
)
from app.judge.llm_judge import LLMJudgeEvaluator


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, type[BaseEvaluator]] = {}

    def register(self, evaluator_cls: type[BaseEvaluator]) -> None:
        self._registry[evaluator_cls.name] = evaluator_cls

    def names(self) -> list[str]:
        return sorted(self._registry)

    def versions(self) -> dict[str, str]:
        return {name: cls.version for name, cls in self._registry.items()}

    def build(self, name: str, deps: dict[str, Any] | None = None) -> BaseEvaluator:
        cls = self._registry.get(name)
        if cls is None:
            raise EvaluatorError(f"Unknown evaluator: {name}")
        return cls(deps)


def default_registry() -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    for cls in (
        ExactMatchEvaluator,
        CaseInsensitiveExactMatchEvaluator,
        ContainsEvaluator,
        RegexEvaluator,
        JsonMatchEvaluator,
        NumericMatchEvaluator,
        LengthEvaluator,
        SafetyRefusalEvaluator,
        LLMJudgeEvaluator,
    ):
        registry.register(cls)
    return registry
