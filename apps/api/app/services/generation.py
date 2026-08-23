"""Test-generation service (Phase 5).

Creates QUEUED GenerationRequest rows with frozen reproducibility snapshots
(generator model snapshot, prompt version, source snapshot), enqueues the
``generate_test_cases`` worker job, and exposes read/cancel/list/candidate
review / dataset-integration operations behind RBAC (ADR-021/022/023).

The worker (GenerationRunner) drives QUEUED → RUNNING → COMPLETED/FAILED and
persists PENDING_REVIEW candidates. Generated test cases are never
automatically trusted: only APPROVED candidates may enter a dataset version.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    ForbiddenError,
    NotFoundError,
    ValidationFailure,
)
from app.core.permissions import CAP_GENERATE_TESTS, require_capability
from app.generation import (
    GENERATION_PROMPT_VERSION,
    validate_candidate_transition,
    validate_generation_config,
    validate_generation_type,
    validate_request_transition,
    validate_source_type,
)
from app.repositories.audit import AuditRepository
from app.repositories.dataset import (
    DatasetRepository,
    DatasetVersionRepository,
    TestCaseRepository,
)
from app.repositories.evaluation import EvaluationRepository, EvaluationResultRepository
from app.repositories.generation import (
    GeneratedCandidateRepository,
    GenerationRequestRepository,
)
from app.repositories.project import ProjectRepository
from app.repositories.provider import ModelRepository, ProviderRepository
from app.schemas.generation import (
    CreateDatasetVersionFromCandidates,
    DatasetVersionFromCandidatesResponse,
    GeneratedCandidateResponse,
    GenerationCreate,
    GenerationResponse,
)
from app.services.dataset import DatasetService
from app.services.organization import OrganizationService
from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue

logger = logging.getLogger("airex.generation")

# Cap the frozen source material embedded in a prompt at 50 records (the dataset
# import limit is 100, so this keeps prompt context bounded and reproducible).
_MAX_SOURCE_RECORDS = 50


async def _enqueue(task: str, payload: dict) -> str:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        queue: TaskQueue = InMemoryTaskQueue()
    else:
        queue = RedisTaskQueue(settings.redis_url)
    job_id = await queue.enqueue(task, payload)
    await queue.close()
    return job_id


class GenerationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._requests = GenerationRequestRepository(session)
        self._candidates = GeneratedCandidateRepository(session)
        self._projects = ProjectRepository(session)
        self._models = ModelRepository(session)
        self._providers = ProviderRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)

    # ------------------------------------------------------------------ authz
    async def _require_member(self, org_id: UUID, user_id: UUID, capability: str):
        role = await self._orgs.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role

    async def _project_in_org(self, project_id: UUID, org_id: UUID) -> bool:
        project = await self._projects.get_by_id(project_id)
        return bool(project and project.organization_id == org_id)

    async def _get_request_in_org(self, request_id: UUID, org_id: UUID):
        request = await self._requests.get_by_id(request_id)
        if request is None or not await self._project_in_org(request.project_id, org_id):
            raise NotFoundError("Generation request was not found.")
        return request

    async def _get_candidate_in_org(self, candidate_id: UUID, org_id: UUID):
        candidate = await self._candidates.get_by_id(candidate_id)
        if candidate is None or not await self._project_in_org(candidate.project_id, org_id):
            raise NotFoundError("Candidate was not found.")
        return candidate

    # --------------------------------------------------------------- create
    async def create(
        self, *, organization_id: UUID, user_id: UUID, payload: GenerationCreate
    ) -> GenerationResponse:
        await self._require_member(organization_id, user_id, CAP_GENERATE_TESTS)
        if not await self._project_in_org(payload.project_id, organization_id):
            raise NotFoundError("Project was not found.")

        source_type = validate_source_type(payload.source_type)
        generation_type = validate_generation_type(payload.generation_type)
        config = validate_generation_config(
            payload.configuration.model_dump(mode="json"), payload.count
        )

        if payload.environment_id is not None:
            from app.repositories.environment import EnvironmentRepository

            env = await EnvironmentRepository(self._session).get_by_id(payload.environment_id)
            if env is None or env.project_id != payload.project_id:
                raise ValidationFailure("Environment does not belong to the project.")

        model = await self._models.get_for_project(payload.generator_model_id, payload.project_id)
        if model is None:
            raise ValidationFailure("Generator model was not found in this project.")
        if not model.is_active:
            raise ValidationFailure("Generator model is not active.")
        provider = await self._providers.get_for_organization(model.provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")

        # Frozen generator-model snapshot (reproducibility; ADR-023).
        merged = {**(provider.metadata_ or {}), **(model.configuration or {})}
        generator_model_snapshot = {
            "model_id": str(model.id),
            "model_identifier": model.model_identifier,
            "provider_id": str(provider.id),
            "provider_type": provider.provider_type,
            "configuration": merged,
            "base_url": provider.base_url,
            "temperature": merged.get("temperature"),
            "max_tokens": merged.get("max_tokens"),
            "top_p": merged.get("top_p"),
            "model_version": (model.updated_at.isoformat() if model.updated_at else "1.0.0"),
        }

        # Validate the source and freeze a source snapshot (records + reference).
        source_snapshot = await self._build_source_snapshot(
            source_type, payload.source_reference, payload.project_id, organization_id
        )

        request = await self._requests.create(
            project_id=payload.project_id,
            environment_id=payload.environment_id,
            source_type=source_type,
            source_reference=source_snapshot.get("source_reference"),
            generation_type=generation_type,
            instruction=payload.instruction,
            count=config["count"],
            configuration=config,
            generator_model_snapshot=generator_model_snapshot,
            prompt_version=GENERATION_PROMPT_VERSION,
            source_snapshot=source_snapshot,
            created_by=user_id,
        )
        await self._audit.record(
            action="GENERATION_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="generation_request",
            resource_id=request.id,
            metadata={
                "source_type": source_type,
                "generation_type": generation_type,
                "count": config["count"],
            },
        )
        await self._session.commit()

        # Queue the worker job (creation auto-queues execution).
        await _enqueue("generate_test_cases", {"generation_request_id": str(request.id)})
        return await self._to_request_response(request)

    async def _build_source_snapshot(
        self,
        source_type: str,
        source_reference: dict | None,
        project_id: UUID,
        organization_id: UUID,
    ) -> dict:
        """Load and freeze the source material for a generation request."""
        reference = dict(source_reference or {})
        if source_type == "MANUAL_INSTRUCTION":
            return {
                "type": "MANUAL_INSTRUCTION",
                "source_reference": None,
                "records": [],
                "record_count": 0,
            }

        versions = DatasetVersionRepository(self._session)
        cases_repo = TestCaseRepository(self._session)

        if source_type == "DATASET":
            version_id = reference.get("dataset_version_id")
            if version_id:
                try:
                    version = await versions.get_by_id(UUID(str(version_id)))
                except ValueError:
                    version = None
            else:
                dataset_id = reference.get("dataset_id")
                if not dataset_id:
                    raise ValidationFailure(
                        "DATASET source requires dataset_id or dataset_version_id."
                    )
                try:
                    version = await versions.latest(UUID(str(dataset_id)))
                except ValueError:
                    version = None
            if version is None:
                raise ValidationFailure("Dataset version was not found.")
            dataset = await DatasetRepository(self._session).get_by_id(version.dataset_id)
            if dataset is None or dataset.project_id != project_id:
                raise ValidationFailure("Dataset version does not belong to the project.")
            cases = await cases_repo.all_for_version(version.id)
            records = self._records_from_cases(cases)
            return {
                "type": "DATASET",
                "source_reference": {
                    "dataset_id": str(dataset.id),
                    "dataset_version_id": str(version.id),
                    "dataset_checksum": version.checksum,
                },
                "records": records,
                "record_count": len(records),
            }

        if source_type == "TEST_CASES":
            raw_ids = reference.get("test_case_ids") or []
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ValidationFailure("TEST_CASES source requires test_case_ids.")
            records = []
            for raw_id in raw_ids:
                try:
                    test_case = await cases_repo.get_by_id(UUID(str(raw_id)))
                except ValueError:
                    test_case = None
                if test_case is None:
                    raise ValidationFailure(f"Test case {raw_id} was not found.")
                version = await versions.get_by_id(test_case.dataset_version_id)
                if version is None:
                    raise ValidationFailure(f"Test case {raw_id} was not found.")
                dataset = await DatasetRepository(self._session).get_by_id(version.dataset_id)
                if dataset is None or dataset.project_id != project_id:
                    raise ValidationFailure(f"Test case {raw_id} does not belong to the project.")
                records.append(self._case_to_record(test_case))
                if len(records) >= _MAX_SOURCE_RECORDS:
                    break
            return {
                "type": "TEST_CASES",
                "source_reference": {"test_case_ids": [r["_id"] for r in records]},
                "records": records,
                "record_count": len(records),
            }

        if source_type == "EVALUATION_FAILURES":
            run_id = reference.get("evaluation_run_id")
            if not run_id:
                raise ValidationFailure("EVALUATION_FAILURES source requires evaluation_run_id.")
            try:
                run = await EvaluationRepository(self._session).get_by_id(UUID(str(run_id)))
            except ValueError:
                run = None
            if run is None or run.project_id != project_id:
                raise ValidationFailure("Evaluation run was not found in this project.")
            results = await EvaluationResultRepository(self._session).all_for_run(run.id)
            records = []
            for result in results:
                if result.status not in ("FAIL", "ERROR"):
                    continue
                if result.test_case_id is None:
                    continue
                test_case = await cases_repo.get_by_id(result.test_case_id)
                if test_case is None:
                    continue
                record = self._case_to_record(test_case)
                record["metadata"] = {
                    "evaluation_result_id": str(result.id),
                    "status": result.status,
                    "failure_type": result.failure_type,
                }
                records.append(record)
                if len(records) >= _MAX_SOURCE_RECORDS:
                    break
            return {
                "type": "EVALUATION_FAILURES",
                "source_reference": {"evaluation_run_id": str(run.id)},
                "records": records,
                "record_count": len(records),
            }

        raise ValidationFailure(f"Unsupported source type: {source_type}")  # pragma: no cover

    def _case_to_record(self, test_case) -> dict:
        return {
            "_id": str(test_case.id),
            "input": test_case.input,
            "expected_output": test_case.expected_output,
            "context": test_case.context,
            "category": test_case.category,
            "difficulty": test_case.difficulty,
            "metadata": test_case.metadata_,
        }

    def _records_from_cases(self, cases: list) -> list[dict]:
        records = [self._case_to_record(c) for c in cases]
        return records[:_MAX_SOURCE_RECORDS]

    # ---------------------------------------------------------------- read
    async def list_requests(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        project_id: UUID | None = None,
        status: str | None = None,
        generation_type: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[GenerationResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        if project_id is not None and not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        if project_id is None:
            return [], 0
        requests, total = await self._requests.list_for_project(
            project_id,
            page=page,
            page_size=page_size,
            status=status,
            generation_type=generation_type,
            source_type=source_type,
        )
        responses = [await self._to_request_response(r) for r in requests]
        return responses, total

    async def get(
        self, *, organization_id: UUID, request_id: UUID, user_id: UUID
    ) -> GenerationResponse:
        await self._require_member(organization_id, user_id, "view_all")
        request = await self._get_request_in_org(request_id, organization_id)
        return await self._to_request_response(request)

    async def cancel(
        self, *, organization_id: UUID, request_id: UUID, user_id: UUID
    ) -> GenerationResponse:
        await self._require_member(organization_id, user_id, CAP_GENERATE_TESTS)
        request = await self._get_request_in_org(request_id, organization_id)
        validate_request_transition(request.status, "CANCELLED")
        await self._requests.set_status(request, "CANCELLED")
        await self._audit.record(
            action="GENERATION_CANCELLED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="generation_request",
            resource_id=request_id,
        )
        await self._session.commit()
        return await self._to_request_response(request)

    # ------------------------------------------------------------ candidates
    async def candidates(
        self,
        *,
        organization_id: UUID,
        request_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        category: str | None = None,
        difficulty: str | None = None,
        generation_type: str | None = None,
    ) -> tuple[list[GeneratedCandidateResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        await self._get_request_in_org(request_id, organization_id)
        candidates, total = await self._candidates.list_for_request(
            request_id,
            page=page,
            page_size=page_size,
            status=status,
            category=category,
            difficulty=difficulty,
            generation_type=generation_type,
        )
        return [self._to_candidate_response(c) for c in candidates], total

    async def get_candidate(
        self, *, organization_id: UUID, candidate_id: UUID, user_id: UUID
    ) -> GeneratedCandidateResponse:
        await self._require_member(organization_id, user_id, "view_all")
        candidate = await self._get_candidate_in_org(candidate_id, organization_id)
        return self._to_candidate_response(candidate)

    async def review_candidate(
        self, *, organization_id: UUID, candidate_id: UUID, user_id: UUID, action: str
    ) -> GeneratedCandidateResponse:
        """Human review: approve or reject a generated candidate (ADR-022)."""
        await self._require_member(organization_id, user_id, CAP_GENERATE_TESTS)
        candidate = await self._get_candidate_in_org(candidate_id, organization_id)
        new_status = "APPROVED" if action.lower() == "approve" else "REJECTED"
        validate_candidate_transition(candidate.status, new_status)
        await self._candidates.set_status(candidate, new_status)
        await self._audit.record(
            action="CANDIDATE_APPROVED" if new_status == "APPROVED" else "CANDIDATE_REJECTED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="generation_candidate",
            resource_id=candidate_id,
        )
        await self._session.commit()
        return self._to_candidate_response(candidate)

    # ------------------------------------------------- dataset integration
    async def create_dataset_version_from_candidates(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        payload: CreateDatasetVersionFromCandidates,
    ) -> DatasetVersionFromCandidatesResponse:
        """Create a dataset version from APPROVED candidates (ADR-022).

        Reuses the Phase 2 dataset pipeline (canonicalize → checksum → store →
        version row → test cases) and tracks consumption on each candidate.
        """
        await self._require_member(organization_id, user_id, CAP_GENERATE_TESTS)
        dataset = await DatasetRepository(self._session).get_by_id(payload.dataset_id)
        if dataset is None or not await self._project_in_org(dataset.project_id, organization_id):
            raise NotFoundError("Dataset was not found.")

        records: list[dict] = []
        candidate_ids: list[UUID] = []
        for candidate_id in payload.candidate_ids:
            candidate = await self._get_candidate_in_org(candidate_id, organization_id)
            if candidate.status != "APPROVED":
                raise ValidationFailure(
                    f"Candidate {candidate_id} is not approved; only approved "
                    "candidates can enter a dataset version."
                )
            if candidate.project_id != dataset.project_id:
                raise ValidationFailure("Candidate does not belong to the dataset's project.")
            if candidate.dataset_version_id is not None:
                raise ValidationFailure(f"Candidate {candidate_id} is already consumed.")
            records.append(
                {
                    "input": candidate.input,
                    "expected_output": candidate.expected_output,
                    "context": candidate.context,
                    "category": candidate.category,
                    "difficulty": candidate.difficulty,
                    "metadata": {
                        "generated": True,
                        "candidate_id": str(candidate.id),
                        "generation_request_id": str(candidate.generation_request_id),
                        "quality_score": candidate.quality_score,
                    },
                }
            )
            candidate_ids.append(candidate.id)

        if not records:
            raise ValidationFailure("No approved candidates were provided.")

        datasets = DatasetService(self._session)
        version = await datasets.create_version_from_records(
            organization_id=organization_id,
            dataset_id=payload.dataset_id,
            user_id=user_id,
            records=records,
        )

        # Track consumption on each approved candidate (post-commit refresh).
        for candidate_id in candidate_ids:
            candidate = await self._candidates.get_by_id(candidate_id)
            if candidate is not None:
                await self._candidates.mark_consumed(candidate, version.id)
        await self._audit.record(
            action="GENERATED_DATASET_VERSION_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="dataset_version",
            resource_id=version.id,
            metadata={
                "dataset_id": str(payload.dataset_id),
                "version_number": version.version_number,
                "record_count": len(records),
            },
        )
        await self._session.commit()
        return DatasetVersionFromCandidatesResponse(
            dataset_version_id=version.id,
            dataset_id=payload.dataset_id,
            version_number=version.version_number,
            record_count=version.record_count,
            checksum=version.checksum,
        )

    # ------------------------------------------------------------- response
    async def _to_request_response(self, request) -> GenerationResponse:
        counts = await self._candidates.counts_by_status(request.id)
        candidate_count = sum(counts.values())
        return GenerationResponse(
            id=request.id,
            project_id=request.project_id,
            environment_id=request.environment_id,
            source_type=request.source_type,
            source_reference=request.source_reference,
            generation_type=request.generation_type,
            instruction=request.instruction,
            count=request.count,
            configuration=request.configuration,
            status=request.status,
            generator_model_snapshot=request.generator_model_snapshot,
            prompt_version=request.prompt_version,
            source_snapshot=request.source_snapshot,
            candidate_count=candidate_count,
            approved_count=counts.get("APPROVED", 0),
            rejected_count=counts.get("REJECTED", 0),
            created_by=request.created_by,
            started_at=request.started_at,
            completed_at=request.completed_at,
            created_at=request.created_at,
        )

    def _to_candidate_response(self, candidate) -> GeneratedCandidateResponse:
        return GeneratedCandidateResponse(
            id=candidate.id,
            generation_request_id=candidate.generation_request_id,
            project_id=candidate.project_id,
            input=candidate.input,
            expected_output=candidate.expected_output,
            context=candidate.context,
            category=candidate.category,
            generation_type=candidate.generation_type,
            difficulty=candidate.difficulty,
            status=candidate.status,
            quality_score=candidate.quality_score,
            fingerprint=candidate.fingerprint,
            duplicate_of=candidate.duplicate_of,
            dataset_version_id=candidate.dataset_version_id,
            metadata=candidate.metadata_,
            created_at=candidate.created_at,
        )
