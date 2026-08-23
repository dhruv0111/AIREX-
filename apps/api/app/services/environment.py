"""Environment service (spec §32–§35; AT-P1-016..018)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import CAP_MANAGE_ENVIRONMENTS, require_capability
from app.repositories.audit import AuditRepository
from app.repositories.environment import EnvironmentRepository
from app.repositories.project import ProjectRepository
from app.schemas.environment import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
)
from app.services.organization import OrganizationService


class EnvironmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._environments = EnvironmentRepository(session)
        self._projects = ProjectRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)

    async def _require_member(self, org_id: UUID, user_id: UUID, capability: str):
        role = await self._orgs.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role

    async def _project_in_org(self, project_id: UUID, org_id: UUID) -> bool:
        project = await self._projects.get_by_id(project_id)
        return bool(project and project.organization_id == org_id)

    async def create(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        payload: EnvironmentCreate,
    ) -> EnvironmentResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_ENVIRONMENTS)
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")

        # One environment per type per project (spec §33; AT-P1-017).
        existing = await self._environments.get_by_type(project_id, payload.environment_type)
        if existing is not None:
            raise ConflictError(
                f"An environment of type {payload.environment_type} already exists "
                "for this project."
            )
        try:
            env = await self._environments.create(
                project_id=project_id,
                name=payload.name,
                environment_type=payload.environment_type,
                default_model_id=payload.default_model_id,
                evaluation_policy=payload.evaluation_policy,
                observability_policy=payload.observability_policy,
                data_retention_policy=payload.data_retention_policy,
            )
        except IntegrityError:
            raise ConflictError("This environment already exists.")
        await self._audit.record(
            action="ENVIRONMENT_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="environment",
            resource_id=env.id,
        )
        await self._session.commit()
        return self._to_response(env)

    async def list(
        self, *, organization_id: UUID, project_id: UUID, user_id: UUID
    ) -> list[EnvironmentResponse]:
        await self._require_member(organization_id, user_id, "view_all")
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        envs = await self._environments.list_for_project(project_id)
        return [self._to_response(e) for e in envs]

    async def get(
        self, *, organization_id: UUID, environment_id: UUID, user_id: UUID
    ) -> EnvironmentResponse:
        await self._require_member(organization_id, user_id, "view_all")
        env = await self._environments.get_by_id(environment_id)
        if env is None or not await self._env_in_org(env, organization_id):
            raise NotFoundError("Environment was not found.")
        return self._to_response(env)

    async def update(
        self,
        *,
        organization_id: UUID,
        environment_id: UUID,
        user_id: UUID,
        payload: EnvironmentUpdate,
    ) -> EnvironmentResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_ENVIRONMENTS)
        env = await self._environments.get_by_id(environment_id)
        if env is None or not await self._env_in_org(env, organization_id):
            raise NotFoundError("Environment was not found.")
        if payload.name is not None:
            env.name = payload.name
        if payload.status is not None:
            env.status = payload.status
        if payload.default_model_id is not None:
            env.default_model_id = payload.default_model_id
        if payload.evaluation_policy is not None:
            env.evaluation_policy = payload.evaluation_policy
        if payload.observability_policy is not None:
            env.observability_policy = payload.observability_policy
        if payload.data_retention_policy is not None:
            env.data_retention_policy = payload.data_retention_policy
        await self._audit.record(
            action="ENVIRONMENT_UPDATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="environment",
            resource_id=environment_id,
        )
        await self._session.commit()
        return self._to_response(env)

    async def delete(self, *, organization_id: UUID, environment_id: UUID, user_id: UUID) -> None:
        await self._require_member(organization_id, user_id, CAP_MANAGE_ENVIRONMENTS)
        env = await self._environments.get_by_id(environment_id)
        if env is None or not await self._env_in_org(env, organization_id):
            raise NotFoundError("Environment was not found.")
        await self._audit.record(
            action="ENVIRONMENT_DELETED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="environment",
            resource_id=environment_id,
        )
        await self._session.delete(env)
        await self._session.commit()

    async def _env_in_org(self, env, organization_id: UUID) -> bool:
        return await self._project_in_org(env.project_id, organization_id)

    def _to_response(self, env) -> EnvironmentResponse:
        return EnvironmentResponse(
            id=env.id,
            project_id=env.project_id,
            name=env.name,
            environment_type=env.environment_type,
            status=env.status,
            default_model_id=env.default_model_id,
            evaluation_policy=env.evaluation_policy,
            observability_policy=env.observability_policy,
            data_retention_policy=env.data_retention_policy,
            created_at=env.created_at,
            updated_at=env.updated_at,
        )
