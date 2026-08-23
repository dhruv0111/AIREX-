"""Model-Gateway-backed LLM judge and its registry evaluator (Phase 4 §7–§8,
§17–§18, §24–§25, §30–§33).

The judge never calls provider SDKs directly; it always goes through
:class:`ModelGatewayService`. Provider failures are surfaced with their original
classification (TIMEOUT / PROVIDER_ERROR) while invalid structured responses
surface as EVALUATOR_ERROR. Judge caching, token tracking and Prometheus metrics
are handled here.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from app.core.encryption import decrypt_credentials
from app.core.metrics import (
    llm_judge_duration_seconds,
    llm_judge_errors_total,
    llm_judge_requests_total,
    llm_judge_tokens_total,
)
from app.evaluators.base import BaseEvaluator, EvaluationScore, EvaluatorError
from app.integrations.gateway import ModelGatewayService
from app.integrations.provider import ErrorCategory, ModelRequest, ProviderError
from app.judge.base import JudgeResult, JudgeRubric
from app.judge.cache import JudgeCache
from app.judge.prompts import JUDGE_PROMPT_VERSION, build_judge_messages
from app.judge.validation import JudgeValidationError, validate_judge_response
from app.repositories.provider import ProviderRepository

_FAILURE_TIMEOUT = "TIMEOUT"
_FAILURE_PROVIDER = "PROVIDER_ERROR"


class ModelGatewayJudge:
    """Provider-independent judge that calls judge models via the Model Gateway."""

    def __init__(
        self,
        *,
        gateway: ModelGatewayService,
        session: Any,
        cache: JudgeCache,
        organization_id: UUID,
    ) -> None:
        self._gateway = gateway
        self._session = session
        self._cache = cache
        self._organization_id = organization_id

    async def _resolve_provider(self, judge_snapshot: dict) -> dict[str, Any]:
        """Resolve the judge provider from the frozen snapshot.

        When a session is available the live provider row is used for credentials;
        otherwise (unit tests with a mock gateway) the snapshot's provider type and
        base URL are used directly. Credentials are never exposed to the judge.
        """
        provider_id = judge_snapshot.get("provider_id")
        if not provider_id:
            raise EvaluatorError("Judge model snapshot has no provider.")
        api_key: str | None = None
        provider_type = judge_snapshot.get("provider_type") or "LOCAL"
        base_url = judge_snapshot.get("base_url")
        if self._session is not None:
            provider = await ProviderRepository(self._session).get_for_organization(
                UUID(str(provider_id)), self._organization_id
            )
            if provider is None:
                raise EvaluatorError("Judge model provider was not found.")
            api_key = (
                decrypt_credentials(provider.encrypted_credentials)
                if provider.encrypted_credentials
                else None
            )
            provider_type = provider.provider_type
            base_url = base_url or getattr(provider, "base_url", None)
        return {"api_key": api_key, "provider_type": provider_type, "base_url": base_url}

    async def evaluate(
        self,
        *,
        input_text: str,
        expected_output: str | None,
        actual_output: str,
        rubric: JudgeRubric,
        context: str | None,
        judge_snapshot: dict,
        reference_required: bool,
        timeout: float,
    ) -> JudgeResult:
        judge_model = str(judge_snapshot.get("model_identifier") or "")
        include_reference = bool(reference_required)
        key = JudgeCache.make_key(
            target_output=actual_output,
            input_text=input_text,
            expected_output=expected_output if include_reference else None,
            context=context,
            rubric_version=rubric.version,
            judge_model=judge_model,
            judge_prompt_version=JUDGE_PROMPT_VERSION,
        )
        cached = await self._cache.get(self._organization_id, key)
        if cached is not None:
            return JudgeResult(
                score=float(cached["score"]),
                passed=bool(cached["passed"]),
                confidence=float(cached["confidence"]),
                reasoning=str(cached["reasoning"]),
                criteria=dict(cached["criteria"]),
                judge_model=judge_model,
                judge_model_version=str(judge_snapshot.get("model_version") or "1.0.0"),
                judge_prompt_version=JUDGE_PROMPT_VERSION,
                rubric_version=rubric.version,
            )

        messages = build_judge_messages(
            input_text=input_text,
            expected_output=expected_output,
            actual_output=actual_output,
            rubric=rubric,
            context=context,
            include_reference=include_reference,
        )
        provider = await self._resolve_provider(judge_snapshot)
        request = ModelRequest(
            model=judge_model,
            messages=messages,
            temperature=judge_snapshot.get("temperature"),
            max_tokens=judge_snapshot.get("max_tokens"),
            top_p=judge_snapshot.get("top_p"),
            timeout=timeout,
        )

        llm_judge_requests_total.inc()
        start = time.perf_counter()
        try:
            response = await self._gateway.invoke(
                provider_type=provider["provider_type"],
                api_key=provider["api_key"],
                base_url=provider["base_url"],
                configuration=judge_snapshot.get("configuration") or {},
                request=request,
            )
        except ProviderError as exc:
            llm_judge_errors_total.inc()
            failure_type = (
                _FAILURE_TIMEOUT
                if exc.category is ErrorCategory.TIMEOUT_ERROR
                else _FAILURE_PROVIDER
            )
            raise EvaluatorError(
                f"Judge model call failed: {exc.message}", failure_type=failure_type
            ) from exc
        finally:
            llm_judge_duration_seconds.observe(time.perf_counter() - start)

        if response.usage is not None and response.usage.total_tokens:
            llm_judge_tokens_total.inc(int(response.usage.total_tokens))

        try:
            validated = validate_judge_response(response.content, rubric)
        except JudgeValidationError as exc:
            llm_judge_errors_total.inc()
            raise EvaluatorError(str(exc)) from exc

        result = JudgeResult(
            score=validated["overall_score"],
            passed=validated["passed"],
            confidence=validated["confidence"],
            reasoning=validated["reasoning"],
            criteria=validated["criteria"],
            judge_model=judge_model,
            judge_model_version=str(judge_snapshot.get("model_version") or "1.0.0"),
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            rubric_version=rubric.version,
            usage=response.usage,
        )
        await self._cache.put(
            self._organization_id,
            key,
            {
                "score": result.score,
                "passed": result.passed,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "criteria": result.criteria,
            },
        )
        return result


class LLMJudgeEvaluator(BaseEvaluator):
    """Registry evaluator ``llm_judge`` (Phase 4 §24, §25, §31).

    The evaluator owns all judge behavior; the runner only builds it with a
    dependency context and awaits ``evaluate_async``. The judge model and rubric
    come from the run's frozen snapshots (reproducibility, ADR-020).
    """

    name = "llm_judge"
    version = "1.0.0"

    def evaluate(
        self, *, expected: str | None, actual: str | None, config: dict[str, Any]
    ) -> EvaluationScore:
        raise EvaluatorError(
            "llm_judge is asynchronous and must be run through the evaluation runner."
        )

    async def evaluate_async(
        self,
        *,
        input_text: str,
        expected_output: str | None,
        actual_output: str,
        context: Any | None,
        config: dict[str, Any],
    ) -> EvaluationScore:
        deps = self._deps
        run = deps.get("run")
        if not run or not run.judge_rubric_snapshot or not run.judge_model_snapshot:
            raise EvaluatorError("LLM judge requires judge snapshots on the evaluation run.")

        rubric = JudgeRubric.from_snapshot(run.judge_rubric_snapshot)
        threshold_value = config.get("threshold")
        threshold = float(threshold_value) if threshold_value is not None else 0.75
        reference_required = bool(config.get("reference_required", True))
        timeout = float(deps.get("timeout") or 30)

        judge = ModelGatewayJudge(
            gateway=deps["gateway"],
            session=deps["session"],
            cache=deps["cache"],
            organization_id=deps["organization_id"],
        )
        result = await judge.evaluate(
            input_text=input_text,
            expected_output=expected_output,
            actual_output=actual_output,
            rubric=rubric,
            context=context,
            judge_snapshot=run.judge_model_snapshot,
            reference_required=reference_required,
            timeout=timeout,
        )

        passed = result.score >= threshold
        return EvaluationScore(
            evaluator=self.name,
            version=self.version,
            score=result.score,
            passed=passed,
            reason=result.reasoning,
            metadata={
                "judge": {
                    "score": result.score,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                    "criteria": result.criteria,
                    "judge_model": result.judge_model,
                    "judge_model_version": result.judge_model_version,
                    "judge_prompt_version": result.judge_prompt_version,
                    "rubric_version": result.rubric_version,
                    "threshold": threshold,
                    "model_snapshot": run.judge_model_snapshot,
                    "rubric_snapshot": run.judge_rubric_snapshot,
                }
            },
        )
