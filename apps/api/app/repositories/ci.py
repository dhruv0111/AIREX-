"""CI and Service Token repositories (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ci import CIRun, ServiceToken


class ServiceTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, token_id: UUID) -> ServiceToken | None:
        return await self._session.get(ServiceToken, token_id)

    async def get_by_hash(self, token_hash: str) -> ServiceToken | None:
        stmt = select(ServiceToken).where(
            and_(
                ServiceToken.token_hash == token_hash,
                ServiceToken.revoked_at.is_(None)
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_for_project(
        self, project_id: UUID, org_id: UUID
    ) -> list[ServiceToken]:
        stmt = select(ServiceToken).where(
            and_(
                ServiceToken.project_id == project_id,
                ServiceToken.organization_id == org_id,
                ServiceToken.revoked_at.is_(None)
            )
        ).order_by(ServiceToken.created_at.desc())
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def create(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        name: str,
        token_hash: str,
        token_prefix: str,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> ServiceToken:
        token = ServiceToken(
            project_id=project_id,
            organization_id=organization_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=scopes,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token


class CIRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, run_id: UUID) -> CIRun | None:
        return await self._session.get(CIRun, run_id)

    async def get_by_idempotency_key(self, key: str) -> CIRun | None:
        stmt = select(CIRun).where(CIRun.idempotency_key == key)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_for_project(
        self, project_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[CIRun], int]:
        base = select(CIRun).where(CIRun.project_id == project_id)
        
        # Use simple count len helper similar to ProjectRepository if standard count isn't imported
        count_res = await self._session.execute(select(CIRun.id).where(CIRun.project_id == project_id))
        total = len(count_res.scalars().all())
        
        res = await self._session.execute(
            base.order_by(CIRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(res.scalars().all()), total

    async def create(
        self,
        *,
        project_id: UUID,
        experiment_id: UUID | None = None,
        experiment_run_id: UUID | None = None,
        commit_sha: str,
        branch: str,
        repository: str,
        pull_request_number: int | None = None,
        pull_request_url: str | None = None,
        ci_provider: str,
        ci_run_id: str,
        ci_job_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CIRun:
        ci_run = CIRun(
            project_id=project_id,
            experiment_id=experiment_id,
            experiment_run_id=experiment_run_id,
            commit_sha=commit_sha,
            branch=branch,
            repository=repository,
            pull_request_number=pull_request_number,
            pull_request_url=pull_request_url,
            ci_provider=ci_provider,
            ci_run_id=ci_run_id,
            ci_job_id=ci_job_id,
            idempotency_key=idempotency_key,
            status="RUNNING",
        )
        self._session.add(ci_run)
        await self._session.flush()
        return ci_run
