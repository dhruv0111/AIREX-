"""Experiment service (Phase 6)."""

from __future__ import annotations

import hashlib
import json
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
from app.core.permissions import CAP_CREATE_EXPERIMENTS, CAP_VIEW_ALL, require_capability
from app.repositories.audit import AuditRepository
from app.repositories.dataset import DatasetVersionRepository, TestCaseRepository
from app.repositories.evaluation import EvaluationRepository
from app.repositories.experiment import ExperimentRepository
from app.repositories.project import ProjectRepository
from app.repositories.provider import ModelRepository, ProviderRepository
from app.repositories.rubric import RubricRepository
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentRunResponse,
    VariantResponse,
    QualityGateResponse,
    ComparisonResponse,
    RegressionResponse,
    QualityGateResultResponse,
)
from app.services.organization import OrganizationService
from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue

logger = logging.getLogger("airex.experiments")


async def _enqueue(task: str, payload: dict) -> str:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        queue: TaskQueue = InMemoryTaskQueue()
    else:
        queue = RedisTaskQueue(settings.redis_url)
    job_id = await queue.enqueue(task, payload)
    await queue.close()
    return job_id


class ExperimentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ExperimentRepository(session)
        self._projects = ProjectRepository(session)
        self._models = ModelRepository(session)
        self._providers = ProviderRepository(session)
        self._versions = DatasetVersionRepository(session)
        self._cases = TestCaseRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)
        self._evals = EvaluationRepository(session)

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

    async def _experiment_in_org(self, experiment, org_id: UUID) -> bool:
        return await self._project_in_org(experiment.project_id, org_id)

    async def _get_experiment_in_org(self, experiment_id: UUID, org_id: UUID):
        experiment = await self._repo.get_by_id(experiment_id)
        if experiment is None or not await self._experiment_in_org(experiment, org_id):
            raise NotFoundError("Experiment was not found.")
        return experiment

    # --------------------------------------------------------------- create
    async def create(
        self, *, organization_id: UUID, user_id: UUID, payload: ExperimentCreate
    ) -> ExperimentResponse:
        await self._require_project_access(organization_id, payload.project_id, user_id, CAP_CREATE_EXPERIMENTS)

        if not await self._project_in_org(payload.project_id, organization_id):
            raise NotFoundError("Project was not found.")

        # Validate variant resources exist and belong to the project/tenant
        # Baseline
        if payload.baseline.model_id:
            m = await self._models.get_by_id(payload.baseline.model_id)
            if m is None or m.project_id != payload.project_id:
                raise ValidationFailure("Baseline model does not belong to the project.")
            if not m.is_active:
                raise ValidationFailure("Baseline model is not active.")
        if payload.baseline.dataset_version_id:
            dv = await self._versions.get_by_id(payload.baseline.dataset_version_id)
            if dv is None:
                raise ValidationFailure("Baseline dataset version was not found.")
        if payload.baseline.prompt_version_id:
            from sqlalchemy import select
            from app.models.experiment import PromptVersion, Prompt
            stmt = (
                select(PromptVersion)
                .join(Prompt, PromptVersion.prompt_id == Prompt.id)
                .where(PromptVersion.id == payload.baseline.prompt_version_id, Prompt.project_id == payload.project_id)
            )
            pv_res = await self._session.execute(stmt)
            if not pv_res.scalars().first():
                raise ValidationFailure("Baseline prompt version does not belong to the project.")

        # Candidate
        if payload.candidate.model_id:
            m = await self._models.get_by_id(payload.candidate.model_id)
            if m is None or m.project_id != payload.project_id:
                raise ValidationFailure("Candidate model does not belong to the project.")
            if not m.is_active:
                raise ValidationFailure("Candidate model is not active.")
        if payload.candidate.dataset_version_id:
            dv = await self._versions.get_by_id(payload.candidate.dataset_version_id)
            if dv is None:
                raise ValidationFailure("Candidate dataset version was not found.")
        if payload.candidate.prompt_version_id:
            from sqlalchemy import select
            from app.models.experiment import PromptVersion, Prompt
            stmt = (
                select(PromptVersion)
                .join(Prompt, PromptVersion.prompt_id == Prompt.id)
                .where(PromptVersion.id == payload.candidate.prompt_version_id, Prompt.project_id == payload.project_id)
            )
            pv_res = await self._session.execute(stmt)
            if not pv_res.scalars().first():
                raise ValidationFailure("Candidate prompt version does not belong to the project.")

        # Compute deterministic configuration fingerprint
        fingerprint_data = {
            "experiment_type": payload.experiment_type,
            "baseline": {
                "model_id": str(payload.baseline.model_id) if payload.baseline.model_id else None,
                "prompt_version_id": str(payload.baseline.prompt_version_id) if payload.baseline.prompt_version_id else None,
                "dataset_version_id": str(payload.baseline.dataset_version_id) if payload.baseline.dataset_version_id else None,
                "configuration": payload.baseline.configuration,
            },
            "candidate": {
                "model_id": str(payload.candidate.model_id) if payload.candidate.model_id else None,
                "prompt_version_id": str(payload.candidate.prompt_version_id) if payload.candidate.prompt_version_id else None,
                "dataset_version_id": str(payload.candidate.dataset_version_id) if payload.candidate.dataset_version_id else None,
                "configuration": payload.candidate.configuration,
            },
            "quality_gates": [
                {
                    "metric_name": qg.metric_name,
                    "gate_type": qg.gate_type,
                    "operator": qg.operator,
                    "threshold": qg.threshold,
                    "is_required": qg.is_required,
                }
                for qg in payload.quality_gates
            ]
        }
        serialized = json.dumps(fingerprint_data, sort_keys=True)
        fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        # Check for duplicate
        dup = await self._repo.find_by_fingerprint(fingerprint)
        dup_id = dup.id if dup else None

        # Create experiment
        experiment = await self._repo.create(
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            experiment_type=payload.experiment_type,
            dataset_version_id=payload.dataset_version_id or payload.baseline.dataset_version_id,
            model_id=payload.model_id or payload.baseline.model_id,
            configuration=payload.configuration,
            fingerprint=fingerprint,
            duplicate_of=dup_id,
            created_by=user_id,
        )

        # Create variants
        baseline_prompt_version_id = payload.baseline.prompt_version_id
        if payload.baseline.prompt_content:
            from app.models.experiment import Prompt, PromptVersion
            from datetime import UTC
            checksum = hashlib.sha256(payload.baseline.prompt_content.encode("utf-8")).hexdigest()
            prompt = Prompt(
                project_id=payload.project_id,
                name=f"{payload.name} - Baseline Prompt",
                description="Auto-created for experiment",
            )
            self._session.add(prompt)
            await self._session.flush()
            pv = PromptVersion(
                prompt_id=prompt.id,
                version_number=1,
                content=payload.baseline.prompt_content,
                checksum=checksum,
                created_at=datetime.now(UTC),
            )
            self._session.add(pv)
            await self._session.flush()
            baseline_prompt_version_id = pv.id

        candidate_prompt_version_id = payload.candidate.prompt_version_id
        if payload.candidate.prompt_content:
            from app.models.experiment import Prompt, PromptVersion
            from datetime import UTC
            checksum = hashlib.sha256(payload.candidate.prompt_content.encode("utf-8")).hexdigest()
            prompt = Prompt(
                project_id=payload.project_id,
                name=f"{payload.name} - Candidate Prompt",
                description="Auto-created for experiment",
            )
            self._session.add(prompt)
            await self._session.flush()
            pv = PromptVersion(
                prompt_id=prompt.id,
                version_number=1,
                content=payload.candidate.prompt_content,
                checksum=checksum,
                created_at=datetime.now(UTC),
            )
            self._session.add(pv)
            await self._session.flush()
            candidate_prompt_version_id = pv.id

        baseline_var = await self._repo.create_variant(
            experiment_id=experiment.id,
            variant_type="BASELINE",
            model_id=payload.baseline.model_id,
            prompt_version_id=baseline_prompt_version_id,
            dataset_version_id=payload.baseline.dataset_version_id,
            configuration=payload.baseline.configuration,
        )

        candidate_var = await self._repo.create_variant(
            experiment_id=experiment.id,
            variant_type="CANDIDATE",
            model_id=payload.candidate.model_id,
            prompt_version_id=candidate_prompt_version_id,
            dataset_version_id=payload.candidate.dataset_version_id,
            configuration=payload.candidate.configuration,
        )

        # Create quality gates
        gates = []
        for qg in payload.quality_gates:
            gate = await self._repo.create_quality_gate(
                experiment_id=experiment.id,
                metric_name=qg.metric_name,
                gate_type=qg.gate_type,
                operator=qg.operator,
                threshold=qg.threshold,
                severity=qg.severity,
                is_required=qg.is_required,
            )
            gates.append(gate)

        await self._audit.record(
            action="EXPERIMENT_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="experiment",
            resource_id=experiment.id,
        )
        for g in gates:
            await self._audit.record(
                action="QUALITY_GATE_CREATED",
                organization_id=organization_id,
                user_id=user_id,
                resource_type="quality_gate",
                resource_id=g.id,
            )

        await self._session.commit()
        return await self._to_experiment_response(experiment)

    # ----------------------------------------------------------------- read
    async def list_experiments(
        self, *, organization_id: UUID, project_id: UUID, user_id: UUID
    ) -> list[ExperimentResponse]:
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        await self._require_project_access(organization_id, project_id, user_id, CAP_VIEW_ALL)

        experiments = await self._repo.list_for_project(project_id)
        res = []
        for exp in experiments:
            res.append(await self._to_experiment_response(exp))
        return res

    async def get(
        self, *, organization_id: UUID, experiment_id: UUID, user_id: UUID
    ) -> ExperimentResponse:
        exp = await self._get_experiment_in_org(experiment_id, organization_id)
        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_VIEW_ALL)
        return await self._to_experiment_response(exp)

    async def delete_experiment(
        self, *, organization_id: UUID, experiment_id: UUID, user_id: UUID
    ) -> None:
        exp = await self._get_experiment_in_org(experiment_id, org_id=organization_id)
        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_CREATE_EXPERIMENTS)
        
        await self._repo.delete(exp)
        await self._audit.record(
            action="EXPERIMENT_DELETED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="experiment",
            resource_id=experiment_id,
        )
        await self._session.commit()

    # ---------------------------------------------------------------- control
    async def start_run(
        self, *, organization_id: UUID, experiment_id: UUID, user_id: UUID
    ) -> ExperimentRunResponse:
        exp = await self._get_experiment_in_org(experiment_id, org_id=organization_id)
        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_CREATE_EXPERIMENTS)

        # Create Run record
        run = await self._repo.create_run(experiment_id=exp.id, created_by=user_id)

        # Update experiment status to QUEUED if it was draft
        if exp.status == "DRAFT":
            await self._repo.set_status(exp, "QUEUED")

        await self._audit.record(
            action="EXPERIMENT_STARTED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="experiment_run",
            resource_id=run.id,
        )
        await self._session.commit()

        # Queue background worker
        await _enqueue("run_experiment", {"experiment_run_id": str(run.id)})

        return self._to_run_response(run)

    async def cancel_run(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> ExperimentRunResponse:
        run = await self._repo.get_run_by_id(run_id)
        if run is None:
            raise NotFoundError("Experiment run was not found.")

        exp = await self._repo.get_by_id(run.experiment_id)
        if exp is None or not await self._experiment_in_org(exp, organization_id):
            raise NotFoundError("Experiment run was not found.")

        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_CREATE_EXPERIMENTS)

        if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
            raise ConflictError("Cannot cancel a completed or already cancelled run.")

        # Update run status to CANCELLED
        await self._repo.set_run_status(run, "CANCELLED")
        await self._repo.set_status(exp, "CANCELLED")

        # Also cancel evaluation runs if they are active
        if run.baseline_run_id:
            try:
                base_run = await self._evals.get_by_id(run.baseline_run_id)
                if base_run and base_run.status in ("QUEUED", "RUNNING"):
                    await self._evals.set_status(base_run, "CANCELLED")
            except Exception:
                pass
        if run.candidate_run_id:
            try:
                cand_run = await self._evals.get_by_id(run.candidate_run_id)
                if cand_run and cand_run.status in ("QUEUED", "RUNNING"):
                    await self._evals.set_status(cand_run, "CANCELLED")
            except Exception:
                pass

        await self._audit.record(
            action="EXPERIMENT_CANCELLED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="experiment_run",
            resource_id=run.id,
        )
        await self._session.commit()
        return self._to_run_response(run)

    # ------------------------------------------------------------- read subres
    async def list_runs(
        self, *, organization_id: UUID, experiment_id: UUID, user_id: UUID
    ) -> list[ExperimentRunResponse]:
        exp = await self._get_experiment_in_org(experiment_id, organization_id)
        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_VIEW_ALL)
        runs = await self._repo.list_runs_for_experiment(exp.id)
        return [self._to_run_response(r) for r in runs]

    async def get_comparisons(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> list[ComparisonResponse]:
        run = await self._repo.get_run_by_id(run_id)
        if run is None:
            raise NotFoundError("Experiment run was not found.")
        exp = await self._repo.get_by_id(run.experiment_id)
        if exp is None or not await self._experiment_in_org(exp, organization_id):
            raise NotFoundError("Experiment run was not found.")

        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_VIEW_ALL)
        comparisons = await self._repo.list_comparisons_for_run(run.id)
        return [self._to_comparison_response(c) for c in comparisons]

    async def get_regressions(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> list[RegressionResponse]:
        run = await self._repo.get_run_by_id(run_id)
        if run is None:
            raise NotFoundError("Experiment run was not found.")
        exp = await self._repo.get_by_id(run.experiment_id)
        if exp is None or not await self._experiment_in_org(exp, organization_id):
            raise NotFoundError("Experiment run was not found.")

        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_VIEW_ALL)
        regressions = await self._repo.list_regressions_for_run(run.id)
        return [self._to_regression_response(r) for r in regressions]

    async def get_gate_results(
        self, *, organization_id: UUID, run_id: UUID, user_id: UUID
    ) -> list[QualityGateResultResponse]:
        run = await self._repo.get_run_by_id(run_id)
        if run is None:
            raise NotFoundError("Experiment run was not found.")
        exp = await self._repo.get_by_id(run.experiment_id)
        if exp is None or not await self._experiment_in_org(exp, organization_id):
            raise NotFoundError("Experiment run was not found.")

        await self._require_project_access(organization_id, exp.project_id, user_id, CAP_VIEW_ALL)

        results = await self._repo.list_gate_results_for_run(run.id)
        return [self._to_gate_result_response(g) for g in results]

    # ------------------------------------------------------------- response
    async def _to_experiment_response(self, exp) -> ExperimentResponse:
        variants = await self._repo.get_variants_for_experiment(exp.id)
        gates = await self._repo.get_quality_gates_for_experiment(exp.id)

        baseline_var = next((v for v in variants if v.variant_type == "BASELINE"), None)
        candidate_var = next((v for v in variants if v.variant_type == "CANDIDATE"), None)

        return ExperimentResponse(
            id=exp.id,
            project_id=exp.project_id,
            name=exp.name,
            description=exp.description,
            dataset_version_id=exp.dataset_version_id,
            model_id=exp.model_id,
            configuration=exp.configuration,
            status=exp.status,
            experiment_type=exp.experiment_type,
            fingerprint=exp.fingerprint,
            duplicate_of=exp.duplicate_of,
            created_by=exp.created_by,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            started_at=exp.started_at,
            completed_at=exp.completed_at,
            baseline=self._to_variant_response(baseline_var) if baseline_var else None,
            candidate=self._to_variant_response(candidate_var) if candidate_var else None,
            quality_gates=[self._to_gate_response(g) for g in gates],
        )

    def _to_variant_response(self, var) -> VariantResponse:
        return VariantResponse(
            id=var.id,
            experiment_id=var.experiment_id,
            variant_type=var.variant_type,
            model_id=var.model_id,
            prompt_version_id=var.prompt_version_id,
            dataset_version_id=var.dataset_version_id,
            configuration=var.configuration,
        )

    def _to_gate_response(self, gate) -> QualityGateResponse:
        return QualityGateResponse(
            id=gate.id,
            experiment_id=gate.experiment_id,
            metric_name=gate.metric_name,
            gate_type=gate.gate_type,
            operator=gate.operator,
            threshold=gate.threshold,
            severity=gate.severity,
            is_required=gate.is_required,
        )

    def _to_run_response(self, run) -> ExperimentRunResponse:
        return ExperimentRunResponse(
            id=run.id,
            experiment_id=run.experiment_id,
            status=run.status,
            baseline_run_id=run.baseline_run_id,
            candidate_run_id=run.candidate_run_id,
            created_by=run.created_by,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
        )

    def _to_comparison_response(self, comp) -> ComparisonResponse:
        return ComparisonResponse(
            id=comp.id,
            run_id=comp.run_id,
            metric_name=comp.metric_name,
            baseline_value=comp.baseline_value,
            candidate_value=comp.candidate_value,
            absolute_difference=comp.absolute_difference,
            relative_difference=comp.relative_difference,
            classification=comp.classification,
            statistical_metadata=comp.statistical_metadata,
        )

    def _to_regression_response(self, reg) -> RegressionResponse:
        return RegressionResponse(
            id=reg.id,
            comparison_id=reg.comparison_id,
            metric_name=reg.metric_name,
            severity=reg.severity,
            baseline_value=reg.baseline_value,
            candidate_value=reg.candidate_value,
            threshold=reg.threshold,
            explanation=reg.explanation,
        )

    def _to_gate_result_response(self, res) -> QualityGateResultResponse:
        return QualityGateResultResponse(
            id=res.id,
            run_id=res.run_id,
            quality_gate_id=res.quality_gate_id,
            metric_name=res.metric_name,
            actual_value=res.actual_value,
            status=res.status,
        )
