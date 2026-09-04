"""Evaluation service (Phase 3 §24–§29, §38–§40, §51–§54).

Creates QUEUED runs with reproducibility snapshots (dataset version + checksum,
model configuration, evaluator versions), enqueues the worker job, and exposes
read/cancel/list operations behind RBAC. The worker (EvaluationRunner) drives
QUEUED → RUNNING → COMPLETED/FAILED.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailure,
)
from app.core.permissions import CAP_RUN_EVALUATIONS, require_capability
from app.evaluations.state import validate_transition
from app.evaluators import default_registry
from app.judge.prompts import JUDGE_PROMPT_VERSION
from app.repositories.audit import AuditRepository
from app.repositories.dataset import DatasetVersionRepository, TestCaseRepository
from app.repositories.evaluation import EvaluationRepository, EvaluationResultRepository
from app.repositories.project import ProjectRepository
from app.repositories.provider import ModelRepository, ProviderRepository
from app.repositories.rubric import RubricRepository
from app.schemas.evaluation import (
    EvaluationCreate,
    EvaluationResponse,
    EvaluationResultResponse,
)
from app.services.organization import OrganizationService
from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue

logger = logging.getLogger("airex.evaluations")


async def _enqueue(task: str, payload: dict) -> str:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        queue: TaskQueue = InMemoryTaskQueue()
    else:
        queue = RedisTaskQueue(settings.redis_url)
    job_id = await queue.enqueue(task, payload)
    await queue.close()
    return job_id


class EvaluationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._runs = EvaluationRepository(session)
        self._results = EvaluationResultRepository(session)
        self._projects = ProjectRepository(session)
        self._models = ModelRepository(session)
        self._providers = ProviderRepository(session)
        self._versions = DatasetVersionRepository(session)
        self._cases = TestCaseRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)
        self._registry = default_registry()
        self._rubrics = RubricRepository(session)

    # ------------------------------------------------------------------ authz
    async def _require_member(self, org_id: UUID, user_id: UUID, capability: str):
        role = await self._orgs.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role

    async def _require_project_access(self, org_id: UUID, project_id: UUID, user_id: UUID, capability: str):
        from app.core.permissions import resolve_user_project_access
        role, _ = await resolve_user_project_access(self._session, user_id, project_id, org_id)
        if role is None:
            raise ForbiddenError("You do not have access to this project.")
        require_capability(role, capability)
        return role

    async def _project_in_org(self, project_id: UUID, org_id: UUID) -> bool:
        project = await self._projects.get_by_id(project_id)
        return bool(project and project.organization_id == org_id)

    async def _run_in_org(self, run, org_id: UUID) -> bool:
        return await self._project_in_org(run.project_id, org_id)

    async def _get_run_in_org(self, run_id: UUID, org_id: UUID):
        run = await self._runs.get_by_id(run_id)
        if run is None or not await self._run_in_org(run, org_id):
            raise NotFoundError("Evaluation was not found.")
        return run

    # --------------------------------------------------------------- create
    async def create(
        self, *, organization_id: UUID, user_id: UUID, payload: EvaluationCreate
    ) -> EvaluationResponse:
        await self._require_project_access(organization_id, payload.project_id, user_id, CAP_RUN_EVALUATIONS)

        # Validate evaluator types against the registry (§14, §22).
        for evaluator in payload.configuration.evaluators:
            if evaluator.type not in self._registry.names():
                raise ValidationFailure(f"Unknown evaluator: {evaluator.type}")

        if not await self._project_in_org(payload.project_id, organization_id):
            raise NotFoundError("Project was not found.")

        if payload.environment_id is not None:
            from app.repositories.environment import EnvironmentRepository

            env = await EnvironmentRepository(self._session).get_by_id(payload.environment_id)
            if env is None or env.project_id != payload.project_id:
                raise ValidationFailure("Environment does not belong to the project.")

        model = await self._models.get_by_id(payload.model_id)
        if model is None or model.project_id != payload.project_id:
            raise ValidationFailure("Model does not belong to the project.")
        if not model.is_active:
            raise ValidationFailure("Model is not active.")

        version = await self._versions.get_by_id(payload.dataset_version_id)
        if version is None:
            raise ValidationFailure("Dataset version was not found.")
        dataset = await self._datasets_for_version(version)
        if dataset is None or dataset.project_id != payload.project_id:
            raise ValidationFailure("Dataset version does not belong to the project.")

        provider = await self._providers.get_for_organization(model.provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")

        # Reproducibility snapshots (§39–§41): frozen at creation, never mutated.
        merged_config = {**(provider.metadata_ or {}), **(model.configuration or {})}
        model_config = {
            "provider_id": str(provider.id),
            "provider_type": provider.provider_type,
            "model_identifier": model.model_identifier,
            "temperature": merged_config.get("temperature"),
            "max_tokens": merged_config.get("max_tokens"),
            "top_p": merged_config.get("top_p"),
            "configuration": merged_config,
            "base_url": provider.base_url,
        }
        evaluator_versions = {
            ev.type: self._registry.versions().get(ev.type)
            for ev in payload.configuration.evaluators
            if ev.type in self._registry.versions()
        }

        # Phase 4 — LLM judge validation + frozen snapshots (§19, §29, §38, ADR-020).
        judge_model_snapshot: dict | None = None
        judge_rubric_snapshot: dict | None = None
        judge_model_id: UUID | None = None
        judge_rubric_id: UUID | None = None
        judge_prompt_version: str | None = None
        for evaluator in payload.configuration.evaluators:
            if evaluator.type != "llm_judge":
                continue
            if evaluator.judge_model_id is None or evaluator.rubric_id is None:
                raise ValidationFailure("llm_judge requires judge_model_id and rubric_id.")
            judge_model = await self._models.get_for_project(
                evaluator.judge_model_id, payload.project_id
            )
            if judge_model is None:
                raise ValidationFailure("Judge model was not found in this project.")
            if not judge_model.is_active:
                raise ValidationFailure("Judge model is not active.")
            judge_provider = await self._providers.get_for_organization(
                judge_model.provider_id, organization_id
            )
            if judge_provider is None:
                raise ValidationFailure("Judge model provider is not configured.")
            rubric = await self._rubrics.get_for_project(evaluator.rubric_id, payload.project_id)
            if rubric is None:
                raise ValidationFailure("Rubric was not found in this project.")
            if rubric.status != "ACTIVE":
                raise ValidationFailure("Rubric is not active.")
            judge_merged = {**(judge_provider.metadata_ or {}), **(judge_model.configuration or {})}
            judge_model_snapshot = {
                "model_id": str(judge_model.id),
                "model_identifier": judge_model.model_identifier,
                "provider_id": str(judge_provider.id),
                "provider_type": judge_provider.provider_type,
                "configuration": judge_merged,
                "base_url": judge_provider.base_url,
                "temperature": judge_merged.get("temperature"),
                "max_tokens": judge_merged.get("max_tokens"),
                "top_p": judge_merged.get("top_p"),
                "model_version": (
                    judge_model.updated_at.isoformat() if judge_model.updated_at else "1.0.0"
                ),
            }
            judge_rubric_snapshot = {
                "rubric_id": str(rubric.id),
                "name": rubric.name,
                "description": rubric.description,
                "version": rubric.version,
                "criteria": rubric.criteria,
            }
            judge_model_id = judge_model.id
            judge_rubric_id = rubric.id
            judge_prompt_version = JUDGE_PROMPT_VERSION

        total_tests = len(await self._cases.all_for_version(version.id))

        run = await self._runs.create(
            project_id=payload.project_id,
            environment_id=payload.environment_id,
            dataset_version_id=version.id,
            model_id=model.id,
            configuration=payload.configuration.model_dump(mode="json"),
            model_config=model_config,
            dataset_checksum=version.checksum,
            evaluator_versions=evaluator_versions,
            total_tests=total_tests,
            created_by=user_id,
            judge_model_id=judge_model_id,
            judge_rubric_id=judge_rubric_id,
            judge_model_snapshot=judge_model_snapshot,
            judge_rubric_snapshot=judge_rubric_snapshot,
            judge_prompt_version=judge_prompt_version,
        )
        await self._audit.record(
            action="EVALUATION_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="evaluation_run",
            resource_id=run.id,
        )
        await self._session.commit()

        # Queue the worker job (creation auto-queues execution, §24–§25).
        await _enqueue("run_evaluation", {"evaluation_run_id": str(run.id)})
        return self._to_run_response(run)

    async def _datasets_for_version(self, version):
        from app.repositories.dataset import DatasetRepository

        return await DatasetRepository(self._session).get_by_id(version.dataset_id)

    # ---------------------------------------------------------------- read
    async def list_runs(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        project_id: UUID | None = None,
        status: str | None = None,
        model_id: UUID | None = None,
        dataset_version_id: UUID | None = None,
    ) -> tuple[list[EvaluationResponse], int]:
        """List evaluation runs for a project (named ``list_runs`` to avoid
        shadowing the builtin ``list`` in class-scope annotations)."""
        if project_id is not None and not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        if project_id is None:
            return [], 0
        await self._require_project_access(organization_id, project_id, user_id, "view_all")
        runs, total = await self._runs.list_for_project(
            project_id,
            page=page,
            page_size=page_size,
            status=status,
            model_id=model_id,
            dataset_version_id=dataset_version_id,
        )
        return [self._to_run_response(r) for r in runs], total

    async def get(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> EvaluationResponse:
        run = await self._get_run_in_org(run_id, organization_id)
        await self._require_project_access(organization_id, run.project_id, user_id, "view_all")
        return self._to_run_response(run)

    async def results(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        failure_type: str | None = None,
    ) -> tuple[list[EvaluationResultResponse], int]:
        run = await self._get_run_in_org(run_id, organization_id)
        await self._require_project_access(organization_id, run.project_id, user_id, "view_all")
        results, total = await self._results.list_for_run(
            run_id, page=page, page_size=page_size, status=status, failure_type=failure_type
        )
        return [self._to_result_response(r) for r in results], total

    # -------------------------------------------------------------- control
    async def start(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> EvaluationResponse:
        """POST /evaluations/{id}/run — explicitly (re)queue a QUEUED run (§25)."""
        run = await self._get_run_in_org(run_id, organization_id)
        await self._require_project_access(organization_id, run.project_id, user_id, CAP_RUN_EVALUATIONS)
        if run.status != "QUEUED":
            raise ConflictError("Only queued evaluations can be started.")
        await _enqueue("run_evaluation", {"evaluation_run_id": str(run.id)})
        return self._to_run_response(run)

    async def cancel(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> EvaluationResponse:
        run = await self._get_run_in_org(run_id, organization_id)
        await self._require_project_access(organization_id, run.project_id, user_id, CAP_RUN_EVALUATIONS)
        validate_transition(run.status, "CANCELLED")
        await self._runs.set_status(run, "CANCELLED")
        await self._audit.record(
            action="EVALUATION_CANCELLED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="evaluation_run",
            resource_id=run_id,
        )
        await self._session.commit()
        return self._to_run_response(run)

    async def reject_result_mutation(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> None:
        """Results are immutable once the run is terminal (§43, AT-P3-027)."""
        await self._require_member(organization_id, user_id, CAP_RUN_EVALUATIONS)
        await self._get_run_in_org(run_id, organization_id)
        raise ConflictError("Evaluation results are immutable.")

    # ------------------------------------------------------------- response
    def _to_run_response(self, run) -> EvaluationResponse:
        return EvaluationResponse(
            id=run.id,
            project_id=run.project_id,
            environment_id=run.environment_id,
            dataset_version_id=run.dataset_version_id,
            model_id=run.model_id,
            status=run.status,
            configuration=run.configuration,
            model_snapshot=run.model_config,
            dataset_checksum=run.dataset_checksum,
            evaluator_versions=run.evaluator_versions,
            judge_model_id=run.judge_model_id,
            judge_rubric_id=run.judge_rubric_id,
            judge_model_snapshot=run.judge_model_snapshot,
            judge_rubric_snapshot=run.judge_rubric_snapshot,
            judge_prompt_version=run.judge_prompt_version,
            total_tests=run.total_tests,
            completed_tests=run.completed_tests,
            passed_tests=run.passed_tests,
            failed_tests=run.failed_tests,
            error_tests=run.error_tests,
            metrics=run.metrics,
            created_by=run.created_by,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )

    def _to_result_response(self, result) -> EvaluationResultResponse:
        return EvaluationResultResponse(
            id=result.id,
            evaluation_run_id=result.evaluation_run_id,
            test_case_id=result.test_case_id,
            actual_output=result.actual_output,
            score=result.score,
            status=result.status,
            failure_type=result.failure_type,
            failure_message=result.failure_message,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.total_tokens,
            estimated_cost=(
                float(result.estimated_cost) if result.estimated_cost is not None else None
            ),
            explanation=result.explanation,
            judge_score=result.judge_score,
            judge_confidence=result.judge_confidence,
            judge_reasoning=result.judge_reasoning,
            judge_criteria_scores=result.judge_criteria_scores,
            judge_model_snapshot=result.judge_model_snapshot,
            judge_rubric_snapshot=result.judge_rubric_snapshot,
            judge_prompt_version=result.judge_prompt_version,
            combined_score=result.combined_score,
            created_at=result.created_at,
        )
