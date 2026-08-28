"""Observability database repository (Phase 8)."""

from __future__ import annotations

from uuid import UUID, uuid4
import sqlalchemy as sa
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trace import Trace, Span


class ObservabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_trace_by_client_id(self, project_id: UUID, trace_id: str) -> Trace | None:
        stmt = select(Trace).where(
            and_(
                Trace.project_id == project_id,
                Trace.trace_id == trace_id
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_spans_by_trace(self, trace_id: str) -> list[Span]:
        stmt = select(Span).where(Span.trace_id == trace_id).order_by(Span.start_time.asc())
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def insert_traces_batch(self, project_id: UUID, org_id: UUID, traces_data: list[dict]) -> list[Trace]:
        if not traces_data:
            return []

        # Find existing trace_ids in the batch
        client_ids = [t["trace_id"] for t in traces_data]
        stmt = select(Trace.trace_id).where(
            and_(
                Trace.project_id == project_id,
                Trace.trace_id.in_(client_ids)
            )
        )
        res = await self._session.execute(stmt)
        existing_ids = set(res.scalars().all())

        inserted = []
        for td in traces_data:
            if td["trace_id"] in existing_ids:
                continue
            
            trace_model = Trace(
                id=uuid4(),
                project_id=project_id,
                organization_id=org_id,
                trace_id=td["trace_id"],
                environment=td.get("environment", "production"),
                service_name=td.get("service_name"),
                operation_name=td.get("operation_name"),
                status=td.get("status"),
                duration_ms=td.get("duration_ms"),
                error=td.get("error"),
                user_id=td.get("user_id"),
                session_id=td.get("session_id"),
                deployment_version=td.get("deployment_version"),
                git_commit=td.get("git_commit"),
                quality_score=td.get("quality_score"),
                metadata_=td.get("metadata"),
                start_time=td["start_time"],
                end_time=td.get("end_time"),
            )
            self._session.add(trace_model)
            inserted.append(trace_model)
            existing_ids.add(td["trace_id"]) # Prevent duplicate in same batch

        return inserted

    async def insert_spans_batch(self, spans_data: list[dict]) -> list[Span]:
        if not spans_data:
            return []

        # Find existing span_ids within trace scopes in the batch
        # To handle this efficiently, we build a set of (trace_id, span_id)
        span_keys = [(s["trace_id"], s["span_id"]) for s in spans_data]
        
        # We can construct OR conditions, or do a simple query if batch size is small
        # To keep it generic and SQLite-friendly:
        existing_keys = set()
        for trace_id, span_id in span_keys:
            stmt = select(Span).where(
                and_(
                    Span.trace_id == trace_id,
                    Span.span_id == span_id
                )
            )
            res = await self._session.execute(stmt)
            if res.scalars().first():
                existing_keys.add((trace_id, span_id))

        inserted = []
        for sd in spans_data:
            key = (sd["trace_id"], sd["span_id"])
            if key in existing_keys:
                continue

            span_model = Span(
                id=uuid4(),
                trace_id=sd["trace_id"],
                span_id=sd["span_id"],
                parent_span_id=sd.get("parent_span_id"),
                name=sd["name"],
                span_type=sd["span_type"],
                status=sd.get("status", "SUCCESS"),
                error=sd.get("error"),
                attributes=sd.get("attributes"),
                provider=sd.get("provider"),
                model=sd.get("model"),
                input_tokens=sd.get("input_tokens"),
                output_tokens=sd.get("output_tokens"),
                total_tokens=sd.get("total_tokens"),
                estimated_cost=sd.get("estimated_cost"),
                temperature=sd.get("temperature"),
                max_tokens=sd.get("max_tokens"),
                error_category=sd.get("error_category"),
                duration_ms=sd.get("duration_ms"),
                start_time=sd["start_time"],
                end_time=sd.get("end_time"),
            )
            self._session.add(span_model)
            inserted.append(span_model)
            existing_keys.add(key) # Prevent duplicate in same batch

        return inserted

    async def get_traces_paginated(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        status: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        trace_id: str | None = None,
        error_category: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Trace], int]:
        stmt = select(Trace).where(Trace.project_id == project_id)

        # Filters
        if environment:
            stmt = stmt.where(Trace.environment == environment)
        if status:
            stmt = stmt.where(Trace.status == status)
        if trace_id:
            stmt = stmt.where(Trace.trace_id == trace_id)
        if start_time:
            stmt = stmt.where(Trace.start_time >= start_time)
        if end_time:
            stmt = stmt.where(Trace.start_time <= end_time)

        # Join Spans for model/provider/error_category filtering if specified
        if model or provider or error_category:
            span_sub = select(Span.trace_id).distinct()
            if model:
                span_sub = span_sub.where(Span.model == model)
            if provider:
                span_sub = span_sub.where(Span.provider == provider)
            if error_category:
                span_sub = span_sub.where(Span.error_category == error_category)
            stmt = stmt.where(Trace.trace_id.in_(span_sub))

        # Order by start_time descending
        stmt = stmt.order_by(Trace.start_time.desc())

        # Total Count query
        count_stmt = select(sa.func.count()).select_from(stmt.subquery())
        count_res = await self._session.execute(count_stmt)
        total_count = count_res.scalar_one()

        # Limit & Offset
        stmt = stmt.limit(limit).offset(offset)
        res = await self._session.execute(stmt)
        return list(res.scalars().all()), total_count

    async def get_traces_in_range(self, project_id: UUID, start: datetime, end: datetime) -> list[Trace]:
        stmt = select(Trace).where(
            and_(
                Trace.project_id == project_id,
                Trace.start_time >= start,
                Trace.start_time <= end
            )
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def get_spans_for_traces(self, trace_ids: list[str]) -> list[Span]:
        if not trace_ids:
            return []
        stmt = select(Span).where(Span.trace_id.in_(trace_ids))
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

