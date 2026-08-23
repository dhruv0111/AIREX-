"""Environment repository (project-scoped)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Environment


class EnvironmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        environment_type: str,
        default_model_id: UUID | None,
        evaluation_policy: dict | None,
        observability_policy: dict | None,
        data_retention_policy: dict | None,
    ) -> Environment:
        env = Environment(
            project_id=project_id,
            name=name,
            environment_type=environment_type,
            status="ACTIVE",
            default_model_id=default_model_id,
            evaluation_policy=evaluation_policy,
            observability_policy=observability_policy,
            data_retention_policy=data_retention_policy,
        )
        self._session.add(env)
        await self._session.flush()
        return env

    async def get_by_id(self, env_id: UUID) -> Environment | None:
        return await self._session.get(Environment, env_id)

    async def get_for_project(self, env_id: UUID, project_id: UUID) -> Environment | None:
        result = await self._session.execute(
            select(Environment).where(
                Environment.id == env_id, Environment.project_id == project_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_project(self, project_id: UUID) -> list[Environment]:
        result = await self._session.execute(
            select(Environment)
            .where(Environment.project_id == project_id)
            .order_by(Environment.created_at)
        )
        return list(result.scalars().all())

    async def get_by_type(self, project_id: UUID, environment_type: str) -> Environment | None:
        result = await self._session.execute(
            select(Environment).where(
                Environment.project_id == project_id,
                Environment.environment_type == environment_type.upper(),
            )
        )
        return result.scalar_one_or_none()
