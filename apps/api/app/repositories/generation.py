"""Generation request + candidate repositories (tenant-scoped; Phase 5).

Repositories only read/write rows; tenant isolation and state-machine rules are
enforced by :mod:`app.services.generation` and :mod:`app.generation.state`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GeneratedCandidate, GenerationRequest


class GenerationRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        environment_id: UUID | None,
        source_type: str,
        source_reference: dict | None,
        generation_type: str,
        instruction: str | None,
        count: int,
        configuration: dict | None,
        generator_model_snapshot: dict | None,
        prompt_version: str | None,
        source_snapshot: dict | None,
        created_by: UUID | None,
    ) -> GenerationRequest:
        request = GenerationRequest(
            project_id=project_id,
            environment_id=environment_id,
            source_type=source_type,
            source_reference=source_reference,
            generation_type=generation_type,
            instruction=instruction,
            count=count,
            configuration=configuration,
            status="QUEUED",
            generator_model_snapshot=generator_model_snapshot,
            prompt_version=prompt_version,
            source_snapshot=source_snapshot,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._session.add(request)
        await self._session.flush()
        return request

    async def get_by_id(self, generation_request_id: UUID) -> GenerationRequest | None:
        return await self._session.get(GenerationRequest, generation_request_id)

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        generation_type: str | None = None,
        source_type: str | None = None,
    ) -> tuple[list[GenerationRequest], int]:
        base = select(GenerationRequest).where(GenerationRequest.project_id == project_id)
        count = (
            select(func.count())
            .select_from(GenerationRequest)
            .where(GenerationRequest.project_id == project_id)
        )
        if status:
            base = base.where(GenerationRequest.status == status.upper())
            count = count.where(GenerationRequest.status == status.upper())
        if generation_type:
            base = base.where(GenerationRequest.generation_type == generation_type.upper())
            count = count.where(GenerationRequest.generation_type == generation_type.upper())
        if source_type:
            base = base.where(GenerationRequest.source_type == source_type.upper())
            count = count.where(GenerationRequest.source_type == source_type.upper())
        total = (await self._session.execute(count)).scalar_one()
        result = await self._session.execute(
            base.order_by(GenerationRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def set_status(self, request: GenerationRequest, status: str) -> GenerationRequest:
        request.status = status
        if status == "RUNNING" and request.started_at is None:
            request.started_at = datetime.now(UTC)
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            request.completed_at = datetime.now(UTC)
        request.heartbeat_at = datetime.now(UTC)
        return request

    async def touch_heartbeat(self, request: GenerationRequest) -> None:
        request.heartbeat_at = datetime.now(UTC)

    async def stale_requests(
        self, older_than: datetime, limit: int = 50
    ) -> list[GenerationRequest]:
        """Return RUNNING requests whose heartbeat is older than ``older_than``."""
        result = await self._session.execute(
            select(GenerationRequest)
            .where(
                GenerationRequest.status == "RUNNING",
                GenerationRequest.heartbeat_at < older_than,
            )
            .order_by(GenerationRequest.heartbeat_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class GeneratedCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        generation_request_id: UUID,
        project_id: UUID,
        input_text: str,
        expected_output: str | None,
        context: dict | None,
        category: str | None,
        generation_type: str,
        difficulty: str | None,
        status: str,
        quality_score: float | None,
        fingerprint: str,
        duplicate_of: UUID | None = None,
        metadata: dict | None = None,
    ) -> GeneratedCandidate:
        candidate = GeneratedCandidate(
            generation_request_id=generation_request_id,
            project_id=project_id,
            input=input_text,
            expected_output=expected_output,
            context=context,
            category=category,
            generation_type=generation_type,
            difficulty=difficulty,
            status=status,
            quality_score=quality_score,
            fingerprint=fingerprint,
            duplicate_of=duplicate_of,
            metadata_=metadata,
            created_at=datetime.now(UTC),
        )
        self._session.add(candidate)
        await self._session.flush()
        return candidate

    async def get_by_id(self, candidate_id: UUID) -> GeneratedCandidate | None:
        return await self._session.get(GeneratedCandidate, candidate_id)

    async def get_by_fingerprint(
        self, generation_request_id: UUID, fingerprint: str
    ) -> GeneratedCandidate | None:
        result = await self._session.execute(
            select(GeneratedCandidate)
            .where(
                GeneratedCandidate.generation_request_id == generation_request_id,
                GeneratedCandidate.fingerprint == fingerprint,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def counts_by_status(self, generation_request_id: UUID) -> dict[str, int]:
        """Return candidate counts grouped by status (single aggregate query)."""
        rows = await self._session.execute(
            select(GeneratedCandidate.status, func.count())
            .where(GeneratedCandidate.generation_request_id == generation_request_id)
            .group_by(GeneratedCandidate.status)
        )
        return {status: int(count) for status, count in rows.all()}

    async def list_for_request(
        self,
        generation_request_id: UUID,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        category: str | None = None,
        difficulty: str | None = None,
        generation_type: str | None = None,
    ) -> tuple[list[GeneratedCandidate], int]:
        base = select(GeneratedCandidate).where(
            GeneratedCandidate.generation_request_id == generation_request_id
        )
        count = (
            select(func.count())
            .select_from(GeneratedCandidate)
            .where(GeneratedCandidate.generation_request_id == generation_request_id)
        )
        if status:
            base = base.where(GeneratedCandidate.status == status.upper())
            count = count.where(GeneratedCandidate.status == status.upper())
        if category:
            base = base.where(GeneratedCandidate.category == category)
            count = count.where(GeneratedCandidate.category == category)
        if difficulty:
            base = base.where(GeneratedCandidate.difficulty == difficulty)
            count = count.where(GeneratedCandidate.difficulty == difficulty)
        if generation_type:
            base = base.where(GeneratedCandidate.generation_type == generation_type.upper())
            count = count.where(GeneratedCandidate.generation_type == generation_type.upper())
        total = (await self._session.execute(count)).scalar_one()
        result = await self._session.execute(
            base.order_by(GeneratedCandidate.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def set_status(self, candidate: GeneratedCandidate, status: str) -> GeneratedCandidate:
        candidate.status = status
        candidate.updated_at = datetime.now(UTC)
        return candidate

    async def mark_consumed(
        self, candidate: GeneratedCandidate, dataset_version_id: UUID
    ) -> GeneratedCandidate:
        candidate.dataset_version_id = dataset_version_id
        candidate.updated_at = datetime.now(UTC)
        return candidate
