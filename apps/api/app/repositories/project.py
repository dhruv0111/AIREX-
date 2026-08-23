"""Project repository (tenant-scoped; every query bounds by organization)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, project_id: UUID) -> Project | None:
        return await self._session.get(Project, project_id)

    async def get_for_organization(self, project_id: UUID, org_id: UUID) -> Project | None:
        """Tenant-scoped fetch (AT-012: cross-org access returns None)."""
        result = await self._session.execute(
            select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, org_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Project], int]:
        base = select(Project).where(Project.organization_id == org_id)
        count_result = await self._session.execute(
            select(Project.id).where(Project.organization_id == org_id)
        )
        total = len(count_result.scalars().all())
        result = await self._session.execute(
            base.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        slug: str,
        description: str | None,
        application_type: str,
        created_by: UUID | None,
    ) -> Project:
        project = Project(
            organization_id=organization_id,
            name=name,
            slug=slug,
            description=description,
            application_type=application_type,
            created_by=created_by,
        )
        self._session.add(project)
        await self._session.flush()
        return project
