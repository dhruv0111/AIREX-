"""Evaluator abstraction (Phase 3 §12–§14, §42; Phase 4 §24–§25, §31).

Every evaluator produces a normalized :class:`EvaluationScore` (evaluator name,
version, normalized score 0.0–1.0, passed, reason). An evaluator raises
:class:`EvaluatorError` for execution problems (e.g. an invalid regex) — the
worker maps that to an ERROR result with failure type EVALUATOR_ERROR without
aborting the whole run. Phase 4 adds optional asynchronous evaluators (the
LLM judge) that receive a dependency context at build time and are awaited by
the runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class EvaluatorError(Exception):
    """Raised when an evaluator cannot execute (e.g. invalid regex/config).

    ``failure_type`` may be set by provider-backed evaluators (e.g. the LLM
    judge) to surface the underlying failure classification (TIMEOUT /
    PROVIDER_ERROR) instead of the generic EVALUATOR_ERROR.
    """

    def __init__(self, message: str, *, failure_type: str | None = None) -> None:
        super().__init__(message)
        self.failure_type = failure_type


@dataclass
class EvaluationScore:
    evaluator: str
    version: str
    score: float  # normalized 0.0 .. 1.0
    passed: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Evaluator(Protocol):
    """Protocol implemented by all evaluators."""

    name: str
    version: str

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore: ...


class BaseEvaluator:
    """Shared base with helper constructors.

    Concrete evaluators implement the synchronous :meth:`evaluate` or (for
    provider-backed evaluators such as the LLM judge) the asynchronous
    :meth:`evaluate_async`. ``deps`` is an optional dependency context supplied
    by the runner (session, gateway, cache, run snapshot).
    """

    name: str = "base"
    version: str = "1.0.0"

    def __init__(self, deps: dict[str, Any] | None = None) -> None:
        self._deps = deps or {}

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        """Evaluate ``actual`` output against ``expected`` and produce a score."""
        raise EvaluatorError(f"Evaluator '{self.name}' does not support synchronous evaluation.")

    async def evaluate_async(
        self,
        *,
        input_text: str,
        expected_output: str | None,
        actual_output: str,
        context: Any | None,
        config: dict[str, Any],
    ) -> EvaluationScore:
        """Asynchronous evaluation used by provider-backed evaluators."""
        raise EvaluatorError(f"Evaluator '{self.name}' does not support asynchronous evaluation.")

    def _pass(self, reason: str, metadata: dict[str, Any] | None = None) -> EvaluationScore:
        return EvaluationScore(
            evaluator=self.name,
            version=self.version,
            score=1.0,
            passed=True,
            reason=reason,
            metadata=metadata or {},
        )

    def _fail(self, reason: str, metadata: dict[str, Any] | None = None) -> EvaluationScore:
        return EvaluationScore(
            evaluator=self.name,
            version=self.version,
            score=0.0,
            passed=False,
            reason=reason,
            metadata=metadata or {},
        )
