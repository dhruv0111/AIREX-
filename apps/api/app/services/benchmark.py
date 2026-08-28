"""Benchmark service logic (Phase 9)."""

from __future__ import annotations

import hashlib
import json
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailure
from app.models.benchmark import (
    BenchmarkSuite,
    BenchmarkVersion,
    BenchmarkRun,
    BenchmarkResult,
    ReliabilityEvidence,
    FailureCluster,
    RootCauseRecommendation,
)
from app.repositories.benchmark import BenchmarkRepository
from app.repositories.audit import AuditRepository
from app.schemas.benchmark import (
    BenchmarkSuiteCreate,
    BenchmarkSuiteResponse,
    BenchmarkVersionCreate,
    BenchmarkVersionResponse,
    BenchmarkRunCreate,
    BenchmarkRunResponse,
    BenchmarkResultResponse,
    ReliabilityEvidenceResponse,
    FailureClusterResponse,
    RootCauseRecommendationResponse,
)

logger = logging.getLogger("airex.benchmarks")


async def _enqueue(task: str, payload: dict) -> str:
    from app.core.config import get_settings
    from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        queue: TaskQueue = InMemoryTaskQueue()
    else:
        queue = RedisTaskQueue(settings.redis_url)
    try:
        job_id = await queue.enqueue(task, payload)
        return job_id
    finally:
        await queue.close()


class BenchmarkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BenchmarkRepository(session)

    # ------------------------------------------------------------- Benchmark Suites
    async def create_suite(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        project_id: UUID,
        payload: BenchmarkSuiteCreate,
    ) -> BenchmarkSuiteResponse:
        # Create suite
        suite = await self._repo.create_suite(
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            created_by=user_id,
        )

        # Validate dataset_version_id is present in configuration
        dataset_version_id_raw = payload.configuration.get("dataset_version_id")
        if not dataset_version_id_raw:
            raise ValidationFailure("dataset_version_id is required in benchmark configuration.")
        
        try:
            dataset_version_id = UUID(str(dataset_version_id_raw))
        except ValueError:
            raise ValidationFailure(f"Invalid dataset_version_id format: {dataset_version_id_raw}")

        # Compute SHA-256 fingerprint for configuration
        config_str = json.dumps(payload.configuration, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()

        # Create Version 1
        await self._repo.create_version(
            benchmark_suite_id=suite.id,
            version=1,
            configuration=payload.configuration,
            configuration_hash=config_hash,
            dataset_version_id=dataset_version_id,
            created_by=user_id,
        )

        await AuditRepository(self._session).record(
            action="BENCHMARK_SUITE_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="benchmark_suite",
            resource_id=suite.id,
        )
        await self._session.commit()
        return BenchmarkSuiteResponse.model_validate(suite)

    async def list_suites(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> list[BenchmarkSuiteResponse]:
        suites = await self._repo.list_suites_for_project(project_id)
        return [BenchmarkSuiteResponse.model_validate(s) for s in suites]

    async def get_suite(
        self,
        *,
        organization_id: UUID,
        suite_id: UUID,
        user_id: UUID,
    ) -> BenchmarkSuiteResponse:
        suite = await self._repo.get_suite_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Benchmark suite not found.")
        return BenchmarkSuiteResponse.model_validate(suite)

    # ----------------------------------------------------------- Benchmark Versions
    async def create_version(
        self,
        *,
        organization_id: UUID,
        suite_id: UUID,
        user_id: UUID,
        payload: BenchmarkVersionCreate,
    ) -> BenchmarkVersionResponse:
        suite = await self._repo.get_suite_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Benchmark suite not found.")

        # Resolve next version number
        latest = await self._repo.get_latest_version(suite_id)
        next_ver = (latest.version + 1) if latest else 1

        # Validate dataset_version_id in configuration
        dataset_version_id_raw = payload.configuration.get("dataset_version_id")
        if not dataset_version_id_raw:
            raise ValidationFailure("dataset_version_id is required in benchmark configuration.")
        
        try:
            dataset_version_id = UUID(str(dataset_version_id_raw))
        except ValueError:
            raise ValidationFailure(f"Invalid dataset_version_id format: {dataset_version_id_raw}")

        # Compute hash
        config_str = json.dumps(payload.configuration, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()

        version = await self._repo.create_version(
            benchmark_suite_id=suite_id,
            version=next_ver,
            configuration=payload.configuration,
            configuration_hash=config_hash,
            dataset_version_id=dataset_version_id,
            created_by=user_id,
        )

        await AuditRepository(self._session).record(
            action="BENCHMARK_VERSION_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="benchmark_version",
            resource_id=version.id,
            metadata={"version": next_ver},
        )
        await self._session.commit()
        return BenchmarkVersionResponse.model_validate(version)

    async def list_versions(
        self,
        *,
        organization_id: UUID,
        suite_id: UUID,
        user_id: UUID,
    ) -> list[BenchmarkVersionResponse]:
        suite = await self._repo.get_suite_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Benchmark suite not found.")

        from sqlalchemy import select
        stmt = select(BenchmarkVersion).where(BenchmarkVersion.benchmark_suite_id == suite_id).order_by(BenchmarkVersion.version.desc())
        res = await self._session.execute(stmt)
        versions = list(res.scalars().all())
        return [BenchmarkVersionResponse.model_validate(v) for v in versions]

    # --------------------------------------------------------------- Benchmark Runs
    async def trigger_run(
        self,
        *,
        organization_id: UUID,
        suite_id: UUID,
        user_id: UUID,
        payload: BenchmarkRunCreate,
    ) -> BenchmarkRunResponse:
        suite = await self._repo.get_suite_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Benchmark suite not found.")

        # Determine version
        if payload.benchmark_version_id:
            version = await self._repo.get_version_by_id(payload.benchmark_version_id)
            if version is None:
                raise NotFoundError("Benchmark version not found.")
        else:
            version = await self._repo.get_latest_version(suite_id)
            if version is None:
                raise ValidationFailure("Benchmark suite has no versions configured.")

        # Create run in repository
        run = await self._repo.create_run(
            benchmark_suite_id=suite_id,
            benchmark_version_id=version.id,
            configuration_hash=version.configuration_hash,
            created_by=user_id,
        )

        await AuditRepository(self._session).record(
            action="BENCHMARK_RUN_TRIGGERED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="benchmark_run",
            resource_id=run.id,
        )
        await self._session.commit()

        # Enqueue background task
        await _enqueue("run_benchmark", {"benchmark_run_id": str(run.id)})

        return BenchmarkRunResponse.model_validate(run)

    async def list_runs(
        self,
        *,
        organization_id: UUID,
        suite_id: UUID,
        user_id: UUID,
    ) -> list[BenchmarkRunResponse]:
        suite = await self._repo.get_suite_by_id(suite_id)
        if suite is None:
            raise NotFoundError("Benchmark suite not found.")
        runs = await self._repo.list_runs_for_suite(suite_id)
        return [BenchmarkRunResponse.model_validate(r) for r in runs]

    async def get_run_detail(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        user_id: UUID,
    ) -> dict:
        run = await self._repo.get_run_by_id(run_id)
        if run is None:
            raise NotFoundError("Benchmark run not found.")

        results = await self._repo.list_results_for_run(run_id)
        evidences = await self._repo.list_evidences_for_run(run_id)
        clusters = await self._repo.list_clusters_for_run(run_id)
        recommendation = await self._repo.get_recommendation_for_run(run_id)

        return {
            "run": BenchmarkRunResponse.model_validate(run),
            "results": [BenchmarkResultResponse.model_validate(r) for r in results],
            "evidences": [ReliabilityEvidenceResponse.model_validate(e) for e in evidences],
            "clusters": [FailureClusterResponse.model_validate(c) for c in clusters],
            "recommendation": RootCauseRecommendationResponse.model_validate(recommendation) if recommendation else None,
        }
