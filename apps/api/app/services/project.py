"""Project service (spec §35; AT-011..AT-014)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import (
    CAP_MANAGE_PROJECTS,
    CAP_VIEW_ALL,
    require_capability,
)
from app.repositories.audit import AuditRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.organization import OrganizationService


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._projects = ProjectRepository(session)
        self._orgs = OrganizationRepository(session)
        self._audit = AuditRepository(session)
        self._org_service = OrganizationService(session)

    async def create(
        self, *, organization_id: UUID, user_id: UUID, payload: ProjectCreate
    ) -> ProjectResponse:
        await self._require_member_capability(organization_id, user_id, CAP_MANAGE_PROJECTS)
        assert payload.slug is not None  # model_validator guarantees a slug
        try:
            project = await self._projects.create(
                organization_id=organization_id,
                name=payload.name,
                slug=payload.slug,
                description=payload.description,
                application_type=payload.application_type,
                created_by=user_id,
            )
        except IntegrityError:
            raise ConflictError("A project with this slug already exists in the organization.")
        await self._audit.record(
            action="project.created",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="project",
            resource_id=project.id,
        )
        await self._session.commit()
        return ProjectResponse.model_validate(project, from_attributes=True)

    async def list(
        self, *, organization_id: UUID, user_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[ProjectResponse], int]:
        await self._require_member_capability(organization_id, user_id, CAP_VIEW_ALL)
        projects, total = await self._projects.list_for_organization(
            organization_id, page=page, page_size=page_size
        )
        return (
            [ProjectResponse.model_validate(p, from_attributes=True) for p in projects],
            total,
        )

    async def get(
        self, *, project_id: UUID, organization_id: UUID, user_id: UUID
    ) -> ProjectResponse:
        await self._require_member_capability(organization_id, user_id, CAP_VIEW_ALL)
        project = await self._projects.get_for_organization(project_id, organization_id)
        if project is None:
            raise NotFoundError("Project was not found.")  # AT-012: cross-org hidden
        return ProjectResponse.model_validate(project, from_attributes=True)

    async def update(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        payload: ProjectUpdate,
    ) -> ProjectResponse:
        await self._require_member_capability(organization_id, user_id, CAP_MANAGE_PROJECTS)
        project = await self._projects.get_for_organization(project_id, organization_id)
        if project is None:
            raise NotFoundError("Project was not found.")
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        if payload.application_type is not None:
            project.application_type = payload.application_type
        if payload.status is not None:
            project.status = payload.status
        await self._audit.record(
            action="project.updated",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="project",
            resource_id=project_id,
        )
        await self._session.commit()
        return ProjectResponse.model_validate(project, from_attributes=True)

    async def delete(self, *, project_id: UUID, organization_id: UUID, user_id: UUID) -> None:
        await self._require_member_capability(organization_id, user_id, CAP_MANAGE_PROJECTS)
        project = await self._projects.get_for_organization(project_id, organization_id)
        if project is None:
            raise NotFoundError("Project was not found.")
        await self._audit.record(
            action="project.deleted",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="project",
            resource_id=project_id,
        )
        await self._session.delete(project)
        await self._session.commit()

    async def _require_member_capability(
        self, organization_id: UUID, user_id: UUID, capability: str
    ):
        role = await self._org_service.resolve_membership(organization_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role
