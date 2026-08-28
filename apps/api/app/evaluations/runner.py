"""Evaluation execution runner (Phase 3 §23, §30, §34–§37, §49–§50; Phase 4
§25, §31–§33, §40–§42, §49–§50).

The worker calls :meth:`EvaluationRunner.run` with an evaluation run id. The
runner reuses the Model Gateway (never provider SDKs directly), applies bounded
concurrency, classifies failures, persists idempotent results, aggregates
metrics, and drives the run state machine. Phase 4 adds asynchronous LLM-judge
evaluators (built with a dependency context), combined pass policies
(ANY/ALL/WEIGHTED) and judge metrics/audit. A crashed run is never left
permanently RUNNING: stale-run recovery is provided by :func:`recover_stale_runs`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.encryption import decrypt_credentials
from app.core.metrics import (
    evaluation_duration_seconds,
    evaluation_errors_total,
    evaluation_runs_total,
    evaluation_tests_failed_total,
    evaluation_tests_passed_total,
    evaluation_tests_total,
)
from app.evaluations.aggregate import (
    apply_pass_policy,
    compute_evaluator_metrics,
    compute_run_metrics,
)
from app.evaluators import EvaluatorError, default_registry
from app.integrations.gateway import ModelGatewayService
from app.integrations.provider import ErrorCategory, ModelRequest, ProviderError
from app.judge.cache import JudgeCache
from app.repositories.audit import AuditRepository
from app.repositories.dataset import DatasetVersionRepository, TestCaseRepository
from app.repositories.evaluation import EvaluationRepository, EvaluationResultRepository
from app.repositories.project import ProjectRepository
from app.repositories.provider import ProviderRepository

logger = logging.getLogger("airex.evaluations")

FAILURE_ASSERTION = "ASSERTION_FAILED"
FAILURE_TIMEOUT = "TIMEOUT"
FAILURE_PROVIDER = "PROVIDER_ERROR"
FAILURE_EVALUATOR = "EVALUATOR_ERROR"

# Result statuses (Phase 3 §10).
RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_ERROR = "ERROR"
RESULT_SKIPPED = "SKIPPED"


def _classify_provider_error(exc: ProviderError) -> str:
    if exc.category is ErrorCategory.TIMEOUT_ERROR:
        return FAILURE_TIMEOUT
    return FAILURE_PROVIDER


def _outcome(
    test_case,
    *,
    status: str,
    failure_type: str | None = None,
    failure_message: str | None = None,
    actual: str | None = None,
    score: list | None = None,
    latency_ms: int | None = None,
    tokens: Any | None = None,
    explanation: str | None = None,
    judge_info: dict | None = None,
    combined_score: float | None = None,
) -> dict[str, Any]:
    judge = judge_info or {}
    return {
        "test_case_id": test_case.id,
        "status": status,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "actual_output": actual,
        "score": score,
        "latency_ms": latency_ms,
        "input_tokens": getattr(tokens, "input_tokens", None),
        "output_tokens": getattr(tokens, "output_tokens", None),
        "total_tokens": getattr(tokens, "total_tokens", None),
        "explanation": explanation,
        "judge_score": judge.get("score"),
        "judge_confidence": judge.get("confidence"),
        "judge_reasoning": judge.get("reasoning"),
        "judge_criteria_scores": judge.get("criteria"),
        "judge_model_snapshot": judge.get("model_snapshot"),
        "judge_rubric_snapshot": judge.get("rubric_snapshot"),
        "judge_prompt_version": judge.get("judge_prompt_version"),
        "combined_score": combined_score,
    }


class EvaluationRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._registry = default_registry()
        self._settings = get_settings()
        self._gateway = ModelGatewayService(self._settings)
        self._cache = JudgeCache()

    async def run(self, run_id: UUID) -> dict[str, Any]:
        """Execute an evaluation run. Idempotent for terminal runs (§49).

        ``run_id`` may arrive as a string (worker payload from JSON); normalize
        it to a :class:`uuid.UUID` so the Uuid-typed primary key binds correctly.
        """
        if isinstance(run_id, str):
            run_id = UUID(run_id)
        start = time.perf_counter()
        async with self._session_factory() as session:
            repo = EvaluationRepository(session)
            run = await repo.get_by_id(run_id)
            if run is None:
                return {"status": "NOT_FOUND"}
            if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                # Duplicate/terminal job: no re-execution, no duplicate results.
                return {"status": run.status, "idempotent": True}

            if run.status == "QUEUED":
                await repo.set_status(run, "RUNNING")
                await AuditRepository(session).record(
                    action="EVALUATION_STARTED",
                    organization_id=None,
                    user_id=run.created_by,
                    resource_type="evaluation_run",
                    resource_id=run.id,
                )
                evaluation_runs_total.labels(status="RUNNING").inc()
                await session.commit()

            try:
                return await self._execute(session, run, start)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("evaluation run failed", extra={"run_id": str(run_id)})
                await repo.set_status(run, "FAILED")
                await AuditRepository(session).record(
                    action="EVALUATION_FAILED",
                    organization_id=None,
                    user_id=run.created_by,
                    resource_type="evaluation_run",
                    resource_id=run.id,
                    metadata={"reason": str(exc)[:1000]},
                )
                evaluation_runs_total.labels(status="FAILED").inc()
                await session.commit()
                return {"status": "FAILED"}

    async def _execute(self, session: AsyncSession, run, start: float) -> dict[str, Any]:
        await session.refresh(run)
        
        run_db_id = run.id
        created_by_id = run.created_by
        project_id = run.project_id
        dataset_version_id = run.dataset_version_id

        repo = EvaluationRepository(session)
        versions = DatasetVersionRepository(session)
        cases_repo = TestCaseRepository(session)
        results_repo = EvaluationResultRepository(session)
        providers = ProviderRepository(session)
        projects = ProjectRepository(session)

        version = (
            await versions.get_by_id(dataset_version_id) if dataset_version_id else None
        )
        if version is None:
            raise RuntimeError("Dataset version not found.")
        test_cases = await cases_repo.all_for_version(version.id)

        model_config = run.model_config or {}
        project = await projects.get_by_id(project_id)
        org_id = project.organization_id if project is not None else None
        provider = None
        if model_config.get("provider_id") and org_id is not None:
            # model_config is a JSON snapshot, so provider_id is a string.
            provider = await providers.get_for_organization(
                UUID(str(model_config["provider_id"])), org_id
            )
        api_key = (
            decrypt_credentials(provider.encrypted_credentials)
            if provider is not None and provider.encrypted_credentials
            else None
        )

        execution = (run.configuration or {}).get("execution", {})
        max_concurrency = int(
            execution.get("max_concurrency") or self._settings.evaluation_max_concurrency
        )
        stop_on_error = bool(execution.get("stop_on_error", False))
        judge_configured = any(
            ec.get("type") == "llm_judge" and ec.get("enabled", True)
            for ec in (run.configuration or {}).get("evaluators", [])
        )

        deps = {
            "session": session,
            "gateway": self._gateway,
            "cache": self._cache,
            "organization_id": org_id,
            "run": run,
            "timeout": float(
                execution.get("timeout_seconds") or self._settings.evaluation_timeout_seconds
            ),
        }

        if judge_configured:
            await AuditRepository(session).record(
                action="LLM_JUDGE_EVALUATION_STARTED",
                organization_id=org_id,
                user_id=created_by_id,
                resource_type="evaluation_run",
                resource_id=run_db_id,
            )

        outcomes = await self._execute_test_cases(
            run,
            test_cases,
            model_config,
            provider,
            api_key,
            execution,
            max_concurrency,
            stop_on_error,
            deps,
        )

        # Persist results (idempotent) and update counts.
        persisted = []
        for outcome in outcomes:
            created = await results_repo.create_result(
                run_id=run_db_id,
                test_case_id=outcome["test_case_id"],
                actual_output=outcome["actual_output"],
                score=outcome["score"],
                status=outcome["status"],
                failure_type=outcome["failure_type"],
                failure_message=outcome["failure_message"],
                latency_ms=outcome["latency_ms"],
                input_tokens=outcome["input_tokens"],
                output_tokens=outcome["output_tokens"],
                total_tokens=outcome["total_tokens"],
                explanation=outcome["explanation"],
                judge_score=outcome["judge_score"],
                judge_confidence=outcome["judge_confidence"],
                judge_reasoning=outcome["judge_reasoning"],
                judge_criteria_scores=outcome["judge_criteria_scores"],
                judge_model_snapshot=outcome["judge_model_snapshot"],
                judge_rubric_snapshot=outcome["judge_rubric_snapshot"],
                judge_prompt_version=outcome["judge_prompt_version"],
                combined_score=outcome["combined_score"],
            )
            if created is not None:
                persisted.append(created)

        rows = await results_repo.all_for_run(run_db_id)
        metrics = compute_run_metrics(rows)
        metrics["evaluators"] = compute_evaluator_metrics(rows)

        completed = sum(1 for o in outcomes)
        passed = sum(1 for o in outcomes if o["status"] == RESULT_PASS)
        failed = sum(1 for o in outcomes if o["status"] == RESULT_FAIL)
        errors = sum(1 for o in outcomes if o["status"] == RESULT_ERROR)

        await repo.update_progress(
            run, completed=completed, passed=passed, failed=failed, errors=errors, metrics=metrics
        )
        await repo.set_status(run, "COMPLETED")
        await repo.touch_heartbeat(run)
        await AuditRepository(session).record(
            action="EVALUATION_COMPLETED",
            organization_id=None,
            user_id=created_by_id,
            resource_type="evaluation_run",
            resource_id=run_db_id,
            metadata={"total": completed, "passed": passed, "failed": failed, "errors": errors},
        )
        if judge_configured:
            judge_action = (
                "LLM_JUDGE_EVALUATION_FAILED" if errors else "LLM_JUDGE_EVALUATION_COMPLETED"
            )
            await AuditRepository(session).record(
                action=judge_action,
                organization_id=org_id,
                user_id=created_by_id,
                resource_type="evaluation_run",
                resource_id=run_db_id,
            )
        evaluation_runs_total.labels(status="COMPLETED").inc()
        evaluation_tests_total.inc(completed)
        evaluation_tests_passed_total.inc(passed)
        evaluation_tests_failed_total.inc(failed)
        evaluation_errors_total.inc(errors)
        evaluation_duration_seconds.observe(time.perf_counter() - start)
        await session.commit()
        return {
            "status": "COMPLETED",
            "total": completed,
            "passed": passed,
            "failed": failed,
            "errors": errors,
        }

    async def _execute_test_cases(
        self,
        run,
        test_cases,
        model_config: dict,
        provider,
        api_key: str | None,
        execution: dict,
        max_concurrency: int,
        stop_on_error: bool,
        deps: dict,
    ) -> list[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        for tc in test_cases:
            queue.put_nowait(tc)

        outcomes: list[dict[str, Any]] = []
        stop = asyncio.Event()

        async def worker() -> None:
            while not stop.is_set():
                try:
                    tc = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                outcome = await self._invoke_and_evaluate(
                    run, tc, model_config, provider, api_key, execution, deps
                )
                outcomes.append(outcome)
                if outcome["status"] == RESULT_ERROR and stop_on_error and not stop.is_set():
                    stop.set()
                    while not queue.empty():  # stop scheduling new tests (§35)
                        queue.get_nowait()
                queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(max(1, max_concurrency))]
        await asyncio.gather(*workers)
        return outcomes

    async def _invoke_and_evaluate(
        self,
        run,
        test_case,
        model_config: dict,
        provider,
        api_key: str | None,
        execution: dict,
        deps: dict,
    ) -> dict[str, Any]:
        timeout = float(
            execution.get("timeout_seconds") or self._settings.evaluation_timeout_seconds
        )
        prompt_content = (run.configuration or {}).get("prompt_version_content")
        if prompt_content:
            if "{{input}}" in prompt_content:
                user_content = prompt_content.replace("{{input}}", test_case.input)
                messages = [{"role": "user", "content": user_content}]
            elif "{{ input }}" in prompt_content:
                user_content = prompt_content.replace("{{ input }}", test_case.input)
                messages = [{"role": "user", "content": user_content}]
            else:
                messages = [
                    {"role": "system", "content": prompt_content},
                    {"role": "user", "content": test_case.input},
                ]
        else:
            messages = [{"role": "user", "content": test_case.input}]

        request = ModelRequest(
            model=model_config.get("model_identifier") or "",
            messages=messages,
            temperature=model_config.get("temperature"),
            max_tokens=model_config.get("max_tokens"),
            top_p=model_config.get("top_p"),
            timeout=timeout,
        )
        try:
            response = await self._gateway.invoke(
                provider_type=model_config.get("provider_type") or provider.provider_type,
                api_key=api_key,
                base_url=model_config.get("base_url") or getattr(provider, "base_url", None),
                configuration=model_config.get("configuration") or {},
                request=request,
            )
        except ProviderError as exc:
            return _outcome(
                test_case,
                status=RESULT_ERROR,
                failure_type=_classify_provider_error(exc),
                failure_message=exc.message,
            )

        scores: list[dict[str, Any]] = []
        weights: list[float | None] = []
        judge_info: dict | None = None
        try:
            for evaluator_cfg in (run.configuration or {}).get("evaluators", []):
                if not evaluator_cfg.get("enabled", True):
                    continue
                weights.append(evaluator_cfg.get("weight"))
                evaluator = self._registry.build(evaluator_cfg["type"], deps=deps)
                if evaluator_cfg["type"] == "llm_judge":
                    score = await evaluator.evaluate_async(
                        input_text=test_case.input,
                        expected_output=test_case.expected_output,
                        actual_output=response.content,
                        context=test_case.context,
                        config=evaluator_cfg,
                    )
                    judge_info = score.metadata.get("judge")
                else:
                    score = evaluator.evaluate(
                        expected=test_case.expected_output,
                        actual=response.content,
                        config=evaluator_cfg.get("params") or {},
                    )
                scores.append(asdict(score))
        except EvaluatorError as exc:
            return _outcome(
                test_case,
                status=RESULT_ERROR,
                failure_type=getattr(exc, "failure_type", None) or FAILURE_EVALUATOR,
                failure_message=str(exc),
                actual=response.content,
                latency_ms=response.latency_ms,
                tokens=response.usage,
            )

        if not scores:
            return _outcome(
                test_case,
                status=RESULT_ERROR,
                failure_type=FAILURE_EVALUATOR,
                failure_message="No enabled evaluators configured.",
                actual=response.content,
                latency_ms=response.latency_ms,
                tokens=response.usage,
            )

        pass_policy = execution.get("pass_policy") or "ALL"
        threshold = execution.get("threshold")
        passed, combined_score = apply_pass_policy(
            scores, pass_policy=pass_policy, threshold=threshold, weights=weights
        )
        return _outcome(
            test_case,
            status=RESULT_PASS if passed else RESULT_FAIL,
            failure_type=None if passed else FAILURE_ASSERTION,
            actual=response.content,
            score=scores,
            latency_ms=response.latency_ms,
            tokens=response.usage,
            explanation="; ".join(s["reason"] for s in scores),
            judge_info=judge_info,
            combined_score=combined_score,
        )


async def recover_stale_runs(session_factory) -> int:
    """Mark RUNNING runs with a stale heartbeat as FAILED (§50).

    A simple, documented recovery strategy: any RUNNING evaluation whose
    heartbeat is older than ``evaluation_stale_timeout_seconds`` is considered
    crashed and marked FAILED so it is never permanently stuck.
    """
    settings = get_settings()
    threshold = datetime.now(UTC) - timedelta(seconds=settings.evaluation_stale_timeout_seconds)
    recovered = 0
    async with session_factory() as session:
        repo = EvaluationRepository(session)
        stale = await repo.stale_runs(threshold)
        for run in stale:
            await repo.set_status(run, "FAILED")
            await AuditRepository(session).record(
                action="EVALUATION_FAILED",
                organization_id=None,
                user_id=run.created_by,
                resource_type="evaluation_run",
                resource_id=run.id,
                metadata={"reason": "stale run recovered after worker crash"},
            )
            evaluation_runs_total.labels(status="FAILED").inc()
            recovered += 1
        if stale:
            await session.commit()
    return recovered
