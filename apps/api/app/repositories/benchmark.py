"""Benchmark repositories (tenant-scoped; Phase 9)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.benchmark import (
    BenchmarkSuite,
    BenchmarkVersion,
    BenchmarkRun,
    BenchmarkResult,
    ReliabilityEvidence,
    FailureCluster,
    RootCauseRecommendation,
)


class BenchmarkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- Benchmark Suite
    async def create_suite(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str | None = None,
        created_by: UUID | None = None,
    ) -> BenchmarkSuite:
        suite = BenchmarkSuite(
            project_id=project_id,
            name=name,
            description=description,
            created_by=created_by,
        )
        self._session.add(suite)
        await self._session.flush()
        return suite

    async def get_suite_by_id(self, suite_id: UUID) -> BenchmarkSuite | None:
        return await self._session.get(BenchmarkSuite, suite_id)

    async def list_suites_for_project(self, project_id: UUID) -> list[BenchmarkSuite]:
        stmt = select(BenchmarkSuite).where(BenchmarkSuite.project_id == project_id).order_by(BenchmarkSuite.created_at.desc())
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ----------------------------------------------------------- Benchmark Version
    async def create_version(
        self,
        *,
        benchmark_suite_id: UUID,
        version: int,
        configuration: dict,
        configuration_hash: str,
        dataset_version_id: UUID,
        created_by: UUID | None = None,
    ) -> BenchmarkVersion:
        version_obj = BenchmarkVersion(
            benchmark_suite_id=benchmark_suite_id,
            version=version,
            configuration=configuration,
            configuration_hash=configuration_hash,
            dataset_version_id=dataset_version_id,
            created_by=created_by,
        )
        self._session.add(version_obj)
        await self._session.flush()
        return version_obj

    async def get_latest_version(self, suite_id: UUID) -> BenchmarkVersion | None:
        stmt = (
            select(BenchmarkVersion)
            .where(BenchmarkVersion.benchmark_suite_id == suite_id)
            .order_by(BenchmarkVersion.version.desc())
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_version_by_id(self, version_id: UUID) -> BenchmarkVersion | None:
        return await self._session.get(BenchmarkVersion, version_id)

    async def get_version_by_number(self, suite_id: UUID, version_number: int) -> BenchmarkVersion | None:
        stmt = select(BenchmarkVersion).where(
            and_(
                BenchmarkVersion.benchmark_suite_id == suite_id,
                BenchmarkVersion.version == version_number
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    # --------------------------------------------------------------- Benchmark Run
    async def create_run(
        self,
        *,
        benchmark_suite_id: UUID,
        benchmark_version_id: UUID,
        configuration_hash: str,
        created_by: UUID | None = None,
    ) -> BenchmarkRun:
        run = BenchmarkRun(
            benchmark_suite_id=benchmark_suite_id,
            benchmark_version_id=benchmark_version_id,
            status="QUEUED",
            configuration_hash=configuration_hash,
            created_by=created_by,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run_by_id(self, run_id: UUID) -> BenchmarkRun | None:
        return await self._session.get(BenchmarkRun, run_id)

    async def list_runs_for_suite(self, suite_id: UUID) -> list[BenchmarkRun]:
        stmt = select(BenchmarkRun).where(BenchmarkRun.benchmark_suite_id == suite_id).order_by(BenchmarkRun.created_at.desc())
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def set_run_status(self, run: BenchmarkRun, status: str, error_message: str | None = None) -> None:
        run.status = status
        if status == "RUNNING" and not run.started_at:
            run.started_at = datetime.now(UTC)
        elif status in ("COMPLETED", "FAILED", "CANCELLED"):
            run.completed_at = datetime.now(UTC)
        if error_message:
            run.error_message = error_message[:2000]
        await self._session.flush()

    async def touch_run_heartbeat(self, run: BenchmarkRun) -> None:
        run.heartbeat_at = datetime.now(UTC)
        await self._session.flush()

    async def get_stale_runs(self, threshold: datetime) -> list[BenchmarkRun]:
        stmt = select(BenchmarkRun).where(
            and_(
                BenchmarkRun.status == "RUNNING",
                BenchmarkRun.heartbeat_at < threshold
            )
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------------------ Benchmark Result
    async def create_result(
        self,
        *,
        benchmark_run_id: UUID,
        evaluation_run_id: UUID,
        baseline_run_id: UUID,
        model_id: UUID,
        reliability_score: float,
    ) -> BenchmarkResult:
        result = BenchmarkResult(
            benchmark_run_id=benchmark_run_id,
            evaluation_run_id=evaluation_run_id,
            baseline_run_id=baseline_run_id,
            model_id=model_id,
            reliability_score=reliability_score,
        )
        self._session.add(result)
        await self._session.flush()
        return result

    async def list_results_for_run(self, run_id: UUID) -> list[BenchmarkResult]:
        stmt = select(BenchmarkResult).where(BenchmarkResult.benchmark_run_id == run_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------- Reliability Evidence
    async def create_evidence(
        self,
        *,
        benchmark_run_id: UUID,
        benchmark_result_id: UUID | None,
        metric_name: str,
        baseline_value: float,
        candidate_value: float,
        absolute_change: float,
        relative_change: float,
        sample_size: int,
        p_value: float | None = None,
        effect_size: float | None = None,
        confidence_interval_low: float | None = None,
        confidence_interval_high: float | None = None,
        significance: bool = False,
        confidence: str = "LOW",
    ) -> ReliabilityEvidence:
        evidence = ReliabilityEvidence(
            benchmark_run_id=benchmark_run_id,
            benchmark_result_id=benchmark_result_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            candidate_value=candidate_value,
            absolute_change=absolute_change,
            relative_change=relative_change,
            sample_size=sample_size,
            p_value=p_value,
            effect_size=effect_size,
            confidence_interval_low=confidence_interval_low,
            confidence_interval_high=confidence_interval_high,
            significance=significance,
            confidence=confidence,
        )
        self._session.add(evidence)
        await self._session.flush()
        return evidence

    async def list_evidences_for_run(self, run_id: UUID) -> list[ReliabilityEvidence]:
        stmt = select(ReliabilityEvidence).where(ReliabilityEvidence.benchmark_run_id == run_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------- Failure Clustering
    async def create_failure_cluster(
        self,
        *,
        benchmark_run_id: UUID,
        benchmark_result_id: UUID | None,
        failure_type: str,
        error_message_pattern: str,
        cluster_count: int,
        cluster_percentage: float,
        severity: str = "LOW",
    ) -> FailureCluster:
        cluster = FailureCluster(
            benchmark_run_id=benchmark_run_id,
            benchmark_result_id=benchmark_result_id,
            failure_type=failure_type,
            error_message_pattern=error_message_pattern,
            cluster_count=cluster_count,
            cluster_percentage=cluster_percentage,
            severity=severity,
        )
        self._session.add(cluster)
        await self._session.flush()
        return cluster

    async def list_clusters_for_run(self, run_id: UUID) -> list[FailureCluster]:
        stmt = select(FailureCluster).where(FailureCluster.benchmark_run_id == run_id)
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------- Root Cause & Recommendation
    async def create_recommendation(
        self,
        *,
        benchmark_run_id: UUID,
        benchmark_result_id: UUID | None,
        regression_attribution: str | None = None,
        root_cause_analysis: str,
        root_cause_confidence: str = "LOW",
        recommendation: str,
    ) -> RootCauseRecommendation:
        rec = RootCauseRecommendation(
            benchmark_run_id=benchmark_run_id,
            benchmark_result_id=benchmark_result_id,
            regression_attribution=regression_attribution,
            root_cause_analysis=root_cause_analysis,
            root_cause_confidence=root_cause_confidence,
            recommendation=recommendation,
        )
        self._session.add(rec)
        await self._session.flush()
        return rec

    async def get_recommendation_for_run(self, run_id: UUID) -> RootCauseRecommendation | None:
        stmt = select(RootCauseRecommendation).where(RootCauseRecommendation.benchmark_run_id == run_id).limit(1)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()
