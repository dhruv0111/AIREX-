"""Experiment repositories (tenant-scoped; Phase 6)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Experiment,
    ExperimentComparison,
    ExperimentRun,
    ExperimentVariant,
    QualityGate,
    QualityGateResult,
    Regression,
)


class ExperimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- Experiments
    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str | None = None,
        experiment_type: str = "MODEL_COMPARISON",
        dataset_version_id: UUID | None = None,
        model_id: UUID | None = None,
        configuration: dict | None = None,
        fingerprint: str | None = None,
        duplicate_of: UUID | None = None,
        created_by: UUID | None = None,
    ) -> Experiment:
        experiment = Experiment(
            project_id=project_id,
            name=name,
            description=description,
            experiment_type=experiment_type,
            dataset_version_id=dataset_version_id,
            model_id=model_id,
            configuration=configuration,
            fingerprint=fingerprint,
            duplicate_of=duplicate_of,
            status="DRAFT",
            created_by=created_by,
        )
        self._session.add(experiment)
        await self._session.flush()
        return experiment

    async def get_by_id(self, experiment_id: UUID) -> Experiment | None:
        return await self._session.get(Experiment, experiment_id)

    async def list_for_project(
        self,
        project_id: UUID,
    ) -> list[Experiment]:
        stmt = select(Experiment).where(Experiment.project_id == project_id).order_by(Experiment.created_at.desc())
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def delete(self, experiment: Experiment) -> None:
        await self._session.delete(experiment)
        await self._session.flush()

    async def set_status(
        self, experiment: Experiment, status: str, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        experiment.status = status
        if status == "RUNNING" and experiment.started_at is None:
            experiment.started_at = now
        if status in ("COMPLETED", "FAILED", "CANCELLED", "INCONCLUSIVE"):
            experiment.completed_at = now

    async def touch_heartbeat(self, experiment: Experiment) -> None:
        experiment.heartbeat_at = datetime.now(UTC)

    async def find_by_fingerprint(self, fingerprint: str) -> Experiment | None:
        stmt = select(Experiment).where(Experiment.fingerprint == fingerprint).order_by(Experiment.created_at.asc())
        res = await self._session.execute(stmt)
        return res.scalars().first()

    # ---------------------------------------------------------------- Variants
    async def create_variant(
        self,
        *,
        experiment_id: UUID,
        variant_type: str,
        model_id: UUID | None = None,
        prompt_version_id: UUID | None = None,
        dataset_version_id: UUID | None = None,
        configuration: dict | None = None,
    ) -> ExperimentVariant:
        variant = ExperimentVariant(
            experiment_id=experiment_id,
            variant_type=variant_type,
            model_id=model_id,
            prompt_version_id=prompt_version_id,
            dataset_version_id=dataset_version_id,
            configuration=configuration,
        )
        self._session.add(variant)
        await self._session.flush()
        return variant

    async def get_variants_for_experiment(self, experiment_id: UUID) -> list[ExperimentVariant]:
        stmt = select(ExperimentVariant).where(ExperimentVariant.experiment_id == experiment_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ----------------------------------------------------------- Quality Gates
    async def create_quality_gate(
        self,
        *,
        experiment_id: UUID,
        metric_name: str,
        gate_type: str = "CANDIDATE_VALUE",
        operator: str,
        threshold: float,
        severity: str = "HIGH",
        is_required: bool = True,
    ) -> QualityGate:
        gate = QualityGate(
            experiment_id=experiment_id,
            metric_name=metric_name,
            gate_type=gate_type,
            operator=operator,
            threshold=threshold,
            severity=severity,
            is_required=is_required,
        )
        self._session.add(gate)
        await self._session.flush()
        return gate

    async def get_quality_gates_for_experiment(self, experiment_id: UUID) -> list[QualityGate]:
        stmt = select(QualityGate).where(QualityGate.experiment_id == experiment_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------- Runs
    async def create_run(
        self,
        *,
        experiment_id: UUID,
        created_by: UUID | None = None,
    ) -> ExperimentRun:
        run = ExperimentRun(
            experiment_id=experiment_id,
            status="QUEUED",
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run_by_id(self, run_id: UUID) -> ExperimentRun | None:
        return await self._session.get(ExperimentRun, run_id)

    async def list_runs_for_experiment(
        self,
        experiment_id: UUID,
    ) -> list[ExperimentRun]:
        stmt = select(ExperimentRun).where(ExperimentRun.experiment_id == experiment_id).order_by(ExperimentRun.created_at.desc())
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def set_run_status(
        self, run: ExperimentRun, status: str, now: datetime | None = None
    ) -> None:
        now = now or datetime.now(UTC)
        run.status = status
        if status == "RUNNING" and run.started_at is None:
            run.started_at = now
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            run.completed_at = now

    async def touch_run_heartbeat(self, run: ExperimentRun) -> None:
        run.heartbeat_at = datetime.now(UTC)

    async def set_run_error(self, run: ExperimentRun, error: str) -> None:
        run.error_message = error

    async def get_stale_runs(self, older_than: datetime, limit: int = 50) -> list[ExperimentRun]:
        stmt = (
            select(ExperimentRun)
            .where(
                ExperimentRun.status == "RUNNING",
                ExperimentRun.heartbeat_at < older_than,
            )
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------------------- Comparisons
    async def create_comparison(
        self,
        *,
        run_id: UUID,
        metric_name: str,
        baseline_value: float | None = None,
        candidate_value: float | None = None,
        absolute_difference: float | None = None,
        relative_difference: float | None = None,
        classification: str,
        statistical_metadata: dict | None = None,
    ) -> ExperimentComparison:
        comparison = ExperimentComparison(
            run_id=run_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            absolute_difference=absolute_difference,
            relative_difference=relative_difference,
            classification=classification,
            statistical_metadata=statistical_metadata,
        )
        self._session.add(comparison)
        await self._session.flush()
        return comparison

    async def list_comparisons_for_run(self, run_id: UUID) -> list[ExperimentComparison]:
        stmt = select(ExperimentComparison).where(ExperimentComparison.run_id == run_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------------------- Regressions
    async def create_regression(
        self,
        *,
        comparison_id: UUID,
        metric_name: str,
        severity: str,
        baseline_value: float | None = None,
        candidate_value: float | None = None,
        threshold: float | None = None,
        explanation: str | None = None,
    ) -> Regression:
        regression = Regression(
            comparison_id=comparison_id,
            metric_name=metric_name,
            severity=severity,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            threshold=threshold,
            explanation=explanation,
        )
        self._session.add(regression)
        await self._session.flush()
        return regression

    async def list_regressions_for_run(self, run_id: UUID) -> list[Regression]:
        stmt = (
            select(Regression)
            .join(ExperimentComparison, Regression.comparison_id == ExperimentComparison.id)
            .where(ExperimentComparison.run_id == run_id)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------- Quality Gate Results
    async def create_gate_result(
        self,
        *,
        run_id: UUID,
        quality_gate_id: UUID,
        metric_name: str,
        actual_value: float | None = None,
        status: str,
    ) -> QualityGateResult:
        res = QualityGateResult(
            run_id=run_id,
            quality_gate_id=quality_gate_id,
            metric_name=metric_name,
            actual_value=actual_value,
            status=status,
        )
        self._session.add(res)
        await self._session.flush()
        return res

    async def list_gate_results_for_run(self, run_id: UUID) -> list[QualityGateResult]:
        stmt = select(QualityGateResult).where(QualityGateResult.run_id == run_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())
