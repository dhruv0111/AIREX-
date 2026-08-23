"""Rubric repository (tenant-scoped; Phase 4 §20–§21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvaluationRun, Rubric


class RubricRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str | None,
        criteria: list,
        version: int,
        created_by: UUID,
    ) -> Rubric:
        rubric = Rubric(
            project_id=project_id,
            name=name,
            description=description,
            version=version,
            criteria=criteria,
            status="ACTIVE",
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._session.add(rubric)
        await self._session.flush()
        return rubric

    async def get_by_id(self, rubric_id: UUID) -> Rubric | None:
        return await self._session.get(Rubric, rubric_id)

    async def get_for_project(self, rubric_id: UUID, project_id: UUID) -> Rubric | None:
        result = await self._session.execute(
            select(Rubric).where(Rubric.id == rubric_id, Rubric.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def max_version(self, project_id: UUID, name: str) -> int:
        result = await self._session.execute(
            select(func.max(Rubric.version)).where(
                Rubric.project_id == project_id, Rubric.name == name
            )
        )
        return int(result.scalar_one() or 0)

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[Rubric], int]:
        base = select(Rubric).where(Rubric.project_id == project_id)
        count = select(func.count()).select_from(Rubric).where(Rubric.project_id == project_id)
        if status:
            base = base.where(Rubric.status == status.upper())
            count = count.where(Rubric.status == status.upper())
        total = (await self._session.execute(count)).scalar_one()
        result = await self._session.execute(
            base.order_by(Rubric.name.asc(), Rubric.version.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def archive_family_previous(
        self, project_id: UUID, name: str, except_version: int
    ) -> None:
        result = await self._session.execute(
            select(Rubric).where(
                Rubric.project_id == project_id,
                Rubric.name == name,
                Rubric.version != except_version,
                Rubric.status == "ACTIVE",
            )
        )
        for rubric in result.scalars().all():
            rubric.status = "ARCHIVED"

    async def is_used(self, rubric_id: UUID) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(EvaluationRun)
            .where(EvaluationRun.judge_rubric_id == rubric_id)
        )
        return (result.scalar_one() or 0) > 0

    async def set_status(self, rubric: Rubric, status: str) -> None:
        rubric.status = status
