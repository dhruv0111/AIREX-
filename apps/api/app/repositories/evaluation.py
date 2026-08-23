"""Evaluation run and result repositories (tenant-scoped; Phase 3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvaluationResult, EvaluationRun


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        environment_id: UUID | None,
        dataset_version_id: UUID,
        model_id: UUID,
        configuration: dict,
        model_config: dict,
        dataset_checksum: str,
        evaluator_versions: dict,
        total_tests: int,
        created_by: UUID,
        judge_model_id: UUID | None = None,
        judge_rubric_id: UUID | None = None,
        judge_model_snapshot: dict | None = None,
        judge_rubric_snapshot: dict | None = None,
        judge_prompt_version: str | None = None,
    ) -> EvaluationRun:
        run = EvaluationRun(
            project_id=project_id,
            environment_id=environment_id,
            dataset_version_id=dataset_version_id,
            model_id=model_id,
            status="QUEUED",
            configuration=configuration,
            model_config=model_config,
            dataset_checksum=dataset_checksum,
            evaluator_versions=evaluator_versions,
            total_tests=total_tests,
            created_by=created_by,
            created_at=datetime.now(UTC),
            judge_model_id=judge_model_id,
            judge_rubric_id=judge_rubric_id,
            judge_model_snapshot=judge_model_snapshot,
            judge_rubric_snapshot=judge_rubric_snapshot,
            judge_prompt_version=judge_prompt_version,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: UUID) -> EvaluationRun | None:
        return await self._session.get(EvaluationRun, run_id)

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        model_id: UUID | None = None,
        dataset_version_id: UUID | None = None,
    ) -> tuple[list[EvaluationRun], int]:
        base = select(EvaluationRun).where(EvaluationRun.project_id == project_id)
        count = (
            select(func.count())
            .select_from(EvaluationRun)
            .where(EvaluationRun.project_id == project_id)
        )
        if status:
            base = base.where(EvaluationRun.status == status.upper())
            count = count.where(EvaluationRun.status == status.upper())
        if model_id:
            base = base.where(EvaluationRun.model_id == model_id)
            count = count.where(EvaluationRun.model_id == model_id)
        if dataset_version_id:
            base = base.where(EvaluationRun.dataset_version_id == dataset_version_id)
            count = count.where(EvaluationRun.dataset_version_id == dataset_version_id)
        total = (await self._session.execute(count)).scalar_one()
        result = await self._session.execute(
            base.order_by(EvaluationRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def set_status(
        self, run: EvaluationRun, status: str, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        run.status = status
        if status == "RUNNING" and run.started_at is None:
            run.started_at = now
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            run.completed_at = now

    async def update_progress(
        self,
        run: EvaluationRun,
        *,
        completed: int,
        passed: int,
        failed: int,
        errors: int,
        metrics: dict | None = None,
    ) -> None:
        run.completed_tests = completed
        run.passed_tests = passed
        run.failed_tests = failed
        run.error_tests = errors
        if metrics is not None:
            run.metrics = metrics

    async def touch_heartbeat(self, run: EvaluationRun) -> None:
        run.heartbeat_at = datetime.now(UTC)

    async def stale_runs(self, older_than: datetime, limit: int = 50) -> list[EvaluationRun]:
        result = await self._session.execute(
            select(EvaluationRun)
            .where(
                EvaluationRun.status == "RUNNING",
                EvaluationRun.heartbeat_at < older_than,
            )
            .limit(limit)
        )
        return list(result.scalars().all())


class EvaluationResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists_for_case(self, run_id: UUID, test_case_id: UUID) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(EvaluationResult)
            .where(
                EvaluationResult.evaluation_run_id == run_id,
                EvaluationResult.test_case_id == test_case_id,
            )
        )
        return (result.scalar_one() or 0) > 0

    async def create_result(
        self,
        *,
        run_id: UUID,
        test_case_id: UUID,
        actual_output: str | None,
        score: dict | None,
        status: str,
        failure_type: str | None,
        failure_message: str | None,
        latency_ms: int | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        explanation: str | None = None,
        judge_score: float | None = None,
        judge_confidence: float | None = None,
        judge_reasoning: str | None = None,
        judge_criteria_scores: dict | None = None,
        judge_model_snapshot: dict | None = None,
        judge_rubric_snapshot: dict | None = None,
        judge_prompt_version: str | None = None,
        combined_score: float | None = None,
    ) -> EvaluationResult | None:
        """Insert a result; returns None if a duplicate already exists (§49)."""
        if await self.exists_for_case(run_id, test_case_id):
            return None
        result = EvaluationResult(
            evaluation_run_id=run_id,
            test_case_id=test_case_id,
            actual_output=actual_output,
            score=score,
            status=status,
            failure_type=failure_type,
            failure_message=failure_message,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=None,
            explanation=explanation,
            judge_score=judge_score,
            judge_confidence=judge_confidence,
            judge_reasoning=judge_reasoning,
            judge_criteria_scores=judge_criteria_scores,
            judge_model_snapshot=judge_model_snapshot,
            judge_rubric_snapshot=judge_rubric_snapshot,
            judge_prompt_version=judge_prompt_version,
            combined_score=combined_score,
        )
        self._session.add(result)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            return None
        return result

    async def get_by_id(self, result_id: UUID) -> EvaluationResult | None:
        return await self._session.get(EvaluationResult, result_id)

    async def list_for_run(
        self,
        run_id: UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        failure_type: str | None = None,
    ) -> tuple[list[EvaluationResult], int]:
        base = select(EvaluationResult).where(EvaluationResult.evaluation_run_id == run_id)
        count = (
            select(func.count())
            .select_from(EvaluationResult)
            .where(EvaluationResult.evaluation_run_id == run_id)
        )
        if status:
            base = base.where(EvaluationResult.status == status.upper())
            count = count.where(EvaluationResult.status == status.upper())
        if failure_type:
            base = base.where(EvaluationResult.failure_type == failure_type)
            count = count.where(EvaluationResult.failure_type == failure_type)
        total = (await self._session.execute(count)).scalar_one()
        result = await self._session.execute(
            base.order_by(EvaluationResult.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def all_for_run(self, run_id: UUID) -> list[EvaluationResult]:
        result = await self._session.execute(
            select(EvaluationResult).where(EvaluationResult.evaluation_run_id == run_id)
        )
        return list(result.scalars().all())
