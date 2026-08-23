"""Rubric service (Phase 4 §20–§23, §50)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import CAP_MANAGE_RUBRICS, require_capability
from app.repositories.audit import AuditRepository
from app.repositories.project import ProjectRepository
from app.repositories.rubric import RubricRepository
from app.rubrics.validation import validate_criteria
from app.schemas.rubric import RubricCreate, RubricResponse, RubricUpdate
from app.services.organization import OrganizationService


class RubricService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._rubrics = RubricRepository(session)
        self._projects = ProjectRepository(session)
        self._orgs = OrganizationService(session)
        self._audit = AuditRepository(session)

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

    async def _get_in_org(self, rubric_id: UUID, org_id: UUID):
        rubric = await self._rubrics.get_by_id(rubric_id)
        if rubric is None or not await self._project_in_org(rubric.project_id, org_id):
            raise NotFoundError("Rubric was not found.")
        return rubric

    # ---------------------------------------------------------------- create
    async def create(
        self, *, organization_id: UUID, project_id: UUID, user_id: UUID, payload: RubricCreate
    ) -> RubricResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_RUBRICS)
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        criteria = validate_criteria([c.model_dump() for c in payload.criteria])
        version = await self._rubrics.max_version(project_id, payload.name) + 1
        rubric = await self._rubrics.create(
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            criteria=criteria,
            version=version,
            created_by=user_id,
        )
        await self._rubrics.archive_family_previous(
            project_id, payload.name, except_version=version
        )
        await self._audit.record(
            action="RUBRIC_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="rubric",
            resource_id=rubric.id,
        )
        await self._session.commit()
        return self._to_response(rubric)

    # ------------------------------------------------------------------ read
    async def list(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[RubricResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        rubrics, total = await self._rubrics.list_for_project(
            project_id, page=page, page_size=page_size, status=status
        )
        return [self._to_response(r) for r in rubrics], total

    async def get(self, *, organization_id: UUID, rubric_id: UUID, user_id: UUID) -> RubricResponse:
        await self._require_member(organization_id, user_id, "view_all")
        rubric = await self._get_in_org(rubric_id, organization_id)
        return self._to_response(rubric)

    # ---------------------------------------------------------------- update
    async def update(
        self, *, organization_id: UUID, rubric_id: UUID, user_id: UUID, payload: RubricUpdate
    ) -> RubricResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_RUBRICS)
        rubric = await self._get_in_org(rubric_id, organization_id)
        if await self._rubrics.is_used(rubric_id):
            raise ConflictError(
                "Rubric has been used by an evaluation and is immutable. "
                "Create a new version instead."
            )
        if payload.name is not None:
            rubric.name = payload.name
        if payload.description is not None:
            rubric.description = payload.description
        if payload.criteria is not None:
            rubric.criteria = validate_criteria([c.model_dump() for c in payload.criteria])
        await self._audit.record(
            action="RUBRIC_UPDATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="rubric",
            resource_id=rubric.id,
        )
        await self._session.commit()
        return self._to_response(rubric)

    async def archive(self, *, organization_id: UUID, rubric_id: UUID, user_id: UUID) -> None:
        await self._require_member(organization_id, user_id, CAP_MANAGE_RUBRICS)
        rubric = await self._get_in_org(rubric_id, organization_id)
        await self._rubrics.set_status(rubric, "ARCHIVED")
        await self._audit.record(
            action="RUBRIC_ARCHIVED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="rubric",
            resource_id=rubric.id,
        )
        await self._session.commit()

    # -------------------------------------------------------------- response
    def _to_response(self, rubric) -> RubricResponse:
        return RubricResponse(
            id=rubric.id,
            project_id=rubric.project_id,
            name=rubric.name,
            description=rubric.description,
            version=rubric.version,
            criteria=rubric.criteria,
            status=rubric.status,
            created_by=rubric.created_by,
            created_at=rubric.created_at,
            updated_at=rubric.updated_at,
        )
