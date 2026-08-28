"""CI/CD and Service Token business logic service (Phase 7)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, UTC
from uuid import UUID, uuid4
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, ForbiddenError, NotFoundError, ValidationFailure
from app.core.permissions import CAP_MANAGE_PROJECTS, require_capability
from app.models import Project, Dataset, DatasetVersion, Model, User, ExperimentRun
from app.models.ci import CIRun, ServiceToken
from app.repositories.audit import AuditRepository
from app.repositories.ci import CIRunRepository, ServiceTokenRepository
from app.repositories.project import ProjectRepository
from app.services.organization import OrganizationService
from app.services.experiment import ExperimentService
from app.schemas.experiment import ExperimentCreate, VariantCreate, QualityGateCreate
from app.core.metrics import (
    ci_runs_total,
    ci_run_failures_total,
    service_token_auth_failures_total,
)


class CIService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tokens = ServiceTokenRepository(session)
        self._runs = CIRunRepository(session)
        self._projects = ProjectRepository(session)
        self._orgs = OrganizationService(session)
        self._audit = AuditRepository(session)

    # ------------------------------------------------------------- Token Management
    async def create_token(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        organization_id: UUID,
        name: str,
        scopes: list[str],
        expires_in_days: int | None = None,
    ) -> tuple[ServiceToken, str]:
        # Enforce CAP_MANAGE_PROJECTS
        role = await self._orgs.resolve_membership(organization_id, user_id)
        if not role:
            raise ForbiddenError("User is not a member of the organization.")
        require_capability(role, CAP_MANAGE_PROJECTS)

        # Ensure project belongs to organization
        project = await self._projects.get_for_organization(project_id, organization_id)
        if not project:
            raise NotFoundError("Project not found in organization.")

        # Generate raw token
        raw_token = f"airex_ci_{secrets.token_hex(32)}"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_prefix = raw_token[:15]  # Display 'airex_ci_abc123'

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        token = await self._tokens.create(
            project_id=project_id,
            organization_id=organization_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=scopes,
            expires_at=expires_at,
        )

        await self._audit.record(
            action="CI_TOKEN_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="service_token",
            resource_id=token.id,
            metadata={"name": name, "scopes": scopes},
        )
        await self._session.commit()

        return token, raw_token

    async def list_tokens(
        self, *, project_id: UUID, user_id: UUID, organization_id: UUID
    ) -> list[ServiceToken]:
        # Enforce CAP_MANAGE_PROJECTS or read project settings
        role = await self._orgs.resolve_membership(organization_id, user_id)
        if not role:
            raise ForbiddenError("User is not a member of the organization.")
        require_capability(role, CAP_MANAGE_PROJECTS)

        return await self._tokens.list_for_project(project_id, organization_id)

    async def revoke_token(
        self, *, token_id: UUID, user_id: UUID, organization_id: UUID
    ) -> None:
        token = await self._tokens.get_by_id(token_id)
        if not token:
            raise NotFoundError("Token not found.")

        # Enforce CAP_MANAGE_PROJECTS
        role = await self._orgs.resolve_membership(organization_id, user_id)
        if not role:
            raise ForbiddenError("User is not a member of the organization.")
        require_capability(role, CAP_MANAGE_PROJECTS)

        if token.organization_id != organization_id:
            raise ForbiddenError("Access denied.")

        token.revoked_at = datetime.now(UTC)

        await self._audit.record(
            action="CI_TOKEN_REVOKED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="service_token",
            resource_id=token.id,
            metadata={"name": token.name},
        )
        await self._session.commit()

    async def rotate_token(
        self, *, token_id: UUID, user_id: UUID, organization_id: UUID
    ) -> tuple[ServiceToken, str]:
        token = await self._tokens.get_by_id(token_id)
        if not token:
            raise NotFoundError("Token not found.")

        # Enforce CAP_MANAGE_PROJECTS
        role = await self._orgs.resolve_membership(organization_id, user_id)
        if not role:
            raise ForbiddenError("User is not a member of the organization.")
        require_capability(role, CAP_MANAGE_PROJECTS)

        if token.organization_id != organization_id:
            raise ForbiddenError("Access denied.")

        # Revoke old
        token.revoked_at = datetime.now(UTC)

        await self._audit.record(
            action="CI_TOKEN_ROTATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="service_token",
            resource_id=token.id,
            metadata={"name": token.name},
        )

        # Create new with same details
        raw_token = f"airex_ci_{secrets.token_hex(32)}"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_prefix = raw_token[:15]

        new_token = await self._tokens.create(
            project_id=token.project_id,
            organization_id=token.organization_id,
            name=token.name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=token.scopes,
            expires_at=token.expires_at,
        )
        await self._session.commit()

        return new_token, raw_token

    # ------------------------------------------------------------------ CI Runs API
    async def create_ci_run(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        commit_sha: str,
        branch: str,
        repository: str,
        pull_request_number: int | None = None,
        pull_request_url: str | None = None,
        ci_provider: str,
        ci_run_id: str,
        ci_job_id: str | None = None,
        experiment_config: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> CIRun:
        # 1. Idempotency Check
        if idempotency_key:
            existing = await self._runs.get_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        # 2. Resolve Dataset
        exp_cfg = experiment_config.get("experiment") or {}
        dataset_name = exp_cfg.get("dataset")
        if not dataset_name:
            ci_run_failures_total.labels(category="invalid_configuration").inc()
            raise ValidationFailure("Experiment configuration requires 'dataset' name.", details={"code": 2})

        stmt_dataset = select(Dataset).where(
            and_(Dataset.project_id == project_id, Dataset.name == dataset_name)
        )
        res_dataset = await self._session.execute(stmt_dataset)
        dataset = res_dataset.scalar_one_or_none()
        if not dataset:
            ci_run_failures_total.labels(category="resource_not_found").inc()
            raise NotFoundError(f"Dataset '{dataset_name}' not found under this project.")

        # Resolve latest dataset version
        stmt_version = select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset.id
        ).order_by(DatasetVersion.version_number.desc())
        res_version = await self._session.execute(stmt_version)
        dataset_version = res_version.scalars().first()
        if not dataset_version:
            ci_run_failures_total.labels(category="resource_not_found").inc()
            raise ValidationFailure(f"Dataset '{dataset_name}' has no active dataset versions.")

        # 3. Resolve Models
        baseline_cfg = exp_cfg.get("baseline") or {}
        candidate_cfg = exp_cfg.get("candidate") or {}
        base_model_name = baseline_cfg.get("model")
        cand_model_name = candidate_cfg.get("model")

        if not base_model_name or not cand_model_name:
            ci_run_failures_total.labels(category="invalid_configuration").inc()
            raise ValidationFailure("Experiment baseline and candidate configurations require a 'model' name.", details={"code": 2})

        async def _resolve_model(model_name: str) -> Model:
            stmt = select(Model).where(
                and_(Model.project_id == project_id, (Model.name == model_name) | (Model.model_identifier == model_name))
            )
            res = await self._session.execute(stmt)
            m = res.scalar_one_or_none()
            if not m:
                ci_run_failures_total.labels(category="resource_not_found").inc()
                raise NotFoundError(f"Model '{model_name}' not found under this project.")
            return m

        base_model = await _resolve_model(base_model_name)
        cand_model = await _resolve_model(cand_model_name)

        # 4. Map Quality Gates
        config_gates = experiment_config.get("quality_gates") or []
        gates_create = []
        for gate in config_gates:
            metric = gate.get("metric")
            operator = gate.get("operator")
            threshold = gate.get("threshold")
            if not metric or not operator or threshold is None:
                ci_run_failures_total.labels(category="invalid_configuration").inc()
                raise ValidationFailure("Invalid quality gate rule: metric, operator, and threshold are required.", details={"code": 2})
            
            gates_create.append(
                QualityGateCreate(
                    metric_name=metric,
                    operator=operator.upper(),
                    threshold=float(threshold),
                    severity="CRITICAL" if gate.get("required", True) else "LOW",
                    is_required=gate.get("required", True),
                    gate_type="CANDIDATE_VALUE",
                )
            )

        # 5. Create Experiment
        exp_service = ExperimentService(self._session)
        payload = ExperimentCreate(
            project_id=project_id,
            name=f"CI Run - {commit_sha[:8]}",
            description=f"Automated CI experiment for commit {commit_sha} ({ci_provider})",
            dataset_id=dataset.id,
            dataset_version_id=dataset_version.id,
            baseline=VariantCreate(
                model_id=base_model.id,
                prompt_content=baseline_cfg.get("prompt_content"),
                configuration=baseline_cfg.get("configuration") or {},
            ),
            candidate=VariantCreate(
                model_id=cand_model.id,
                prompt_content=candidate_cfg.get("prompt_content"),
                configuration=candidate_cfg.get("configuration") or {},
            ),
            gates=gates_create,
        )

        experiment = await exp_service.create(
            organization_id=organization_id, user_id=user_id, payload=payload
        )

        # 6. Create CI Run record
        ci_run = await self._runs.create(
            project_id=project_id,
            experiment_id=experiment.id,
            commit_sha=commit_sha,
            branch=branch,
            repository=repository,
            pull_request_number=pull_request_number,
            pull_request_url=pull_request_url,
            ci_provider=ci_provider,
            ci_run_id=ci_run_id,
            ci_job_id=ci_job_id,
            idempotency_key=idempotency_key,
        )

        # 7. Start Run
        run = await exp_service.start_run(
            organization_id=organization_id, experiment_id=experiment.id, user_id=user_id
        )

        ci_run.experiment_run_id = run.id

        await self._audit.record(
            action="CI_RUN_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="ci_run",
            resource_id=ci_run.id,
            metadata={"commit_sha": commit_sha, "branch": branch, "ci_run_id": ci_run_id},
        )
        await self._audit.record(
            action="CI_RUN_STARTED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="ci_run",
            resource_id=ci_run.id,
            metadata={"run_id": str(run.id)},
        )

        ci_runs_total.labels(provider=ci_provider, status="RUNNING").inc()
        await self._session.commit()

        return ci_run

    async def get_ci_run(
        self, *, run_id: UUID, organization_id: UUID
    ) -> CIRun:
        run = await self._runs.get_by_id(run_id)
        if not run:
            raise NotFoundError("CI run not found.")

        # Ensure project bounds match token organization
        project = await self._session.get(Project, run.project_id)
        if not project or project.organization_id != organization_id:
            raise ForbiddenError("Access denied.")

        return run

    async def list_ci_runs(
        self, *, project_id: UUID, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[CIRun], int]:
        # Scopes and boundaries check
        project = await self._projects.get_for_organization(project_id, organization_id)
        if not project:
            raise NotFoundError("Project not found.")

        return await self._runs.list_for_project(project_id, page=page, page_size=page_size)
