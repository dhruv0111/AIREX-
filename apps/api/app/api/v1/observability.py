"""Observability API endpoints (Phase 8)."""

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.errors import ForbiddenError, NotFoundError, ValidationFailure
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.observability import IngestBatchPayload
from app.services.observability import ObservabilityService
from app.workers.queue import InMemoryTaskQueue, RedisTaskQueue, TaskQueue
from app.core.config import get_settings

router = APIRouter()


def _resolve_time_range(
    start_time: str | None,
    end_time: str | None,
    default_hours: float = 24,
) -> tuple[datetime, datetime]:
    """Resolve start/end datetimes, defaulting to the last N hours."""
    if start_time:
        start = datetime.fromisoformat(start_time)
    else:
        start = datetime.now(UTC) - timedelta(hours=default_hours)

    if end_time:
        end = datetime.fromisoformat(end_time)
    else:
        end = datetime.now(UTC)

    return start, end


async def _enqueue(task: str, payload: dict) -> str:
    settings = get_settings()
    if settings.redis_url.startswith("memory://"):
        queue: TaskQueue = InMemoryTaskQueue()
    else:
        queue = RedisTaskQueue(settings.redis_url)
    job_id = await queue.enqueue(task, payload)
    await queue.close()
    return job_id


@router.post("/observability/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_observability(
    payload: IngestBatchPayload,
    request: Request,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batched production observability trace and span ingestion (AT-P8-001/002)."""
    # 1. Reject oversized payloads (AT-P8-029)
    if len(payload.traces) > 1000 or len(payload.spans) > 5000:
        raise ValidationFailure("Payload exceeds maximum allowable batch size.")

    # 2. Resolve project_id boundary context
    project_id = None
    if hasattr(request.state, "is_service_token") and request.state.is_service_token:
        project_id = request.state.service_token_project_id
    else:
        project_id_hdr = request.headers.get("X-Project-Id") or request.query_params.get("project_id")
        if project_id_hdr:
            try:
                project_id = UUID(project_id_hdr)
            except ValueError:
                raise ValidationFailure("Invalid X-Project-Id or project_id parameter.")

    if not project_id:
        raise ValidationFailure("Missing target Project context.")

    project = await db.get(Project, project_id)
    if not project:
        raise ValidationFailure("Project not found.")

    from app.core.permissions import resolve_user_project_access
    role, _ = await resolve_user_project_access(db, user.id, project_id, project.organization_id)
    if role is None:
        raise ForbiddenError("You do not have access to this project.")

    # 3. Asynchronously queue payload for ingestion processing
    job_payload = {
        "project_id": str(project_id),
        "org_id": str(project.organization_id),
        "traces": [t.model_dump(mode="json") for t in payload.traces],
        "spans": [s.model_dump(mode="json") for s in payload.spans],
    }

    job_id = await _enqueue("ingest_observability", job_payload)

    # 4. Increment Prometheus metrics
    from app.core.metrics import (
        airex_observability_ingested_total,
        airex_llm_requests_total,
        airex_llm_tokens_total,
    )
    airex_observability_ingested_total.inc(len(payload.traces) + len(payload.spans))

    for s in payload.spans:
        if s.span_type == "LLM":
            provider = (s.provider or "unknown").lower()
            model = (s.model or "unknown").lower()
            airex_llm_requests_total.labels(provider=provider, model=model).inc()
            if s.total_tokens:
                airex_llm_tokens_total.labels(provider=provider, model=model).inc(s.total_tokens)

    return {"status": "accepted", "job_id": job_id}


@router.get("/projects/{project_id}/observability/overview")
async def get_observability_overview(
    project_id: UUID,
    environment: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Retrieve aggregated overview metrics for production tracing dashboard."""
    start, end = _resolve_time_range(start_time, end_time)
    service = ObservabilityService(db)
    return await service.get_overview(project_id, environment=environment, start_time=start, end_time=end)


@router.get("/projects/{project_id}/observability/models")
async def get_observability_models(
    project_id: UUID,
    environment: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Per-model breakdown: requests, success/error rate, latency, tokens, cost."""
    start, end = _resolve_time_range(start_time, end_time)
    service = ObservabilityService(db)
    return await service.get_models(project_id, environment=environment, start_time=start, end_time=end)


@router.get("/projects/{project_id}/observability/providers")
async def get_observability_providers(
    project_id: UUID,
    environment: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Per-provider breakdown: requests, success/error rate, latency, tokens, cost."""
    start, end = _resolve_time_range(start_time, end_time)
    service = ObservabilityService(db)
    return await service.get_providers(project_id, environment=environment, start_time=start, end_time=end)


@router.get("/projects/{project_id}/observability/cost")
async def get_observability_cost(
    project_id: UUID,
    environment: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Cost dashboard: total cost, cost/request, and breakdowns by model/provider/environment."""
    start, end = _resolve_time_range(start_time, end_time)
    service = ObservabilityService(db)
    return await service.get_cost(project_id, environment=environment, start_time=start, end_time=end)


@router.get("/projects/{project_id}/observability/latency")
async def get_observability_latency(
    project_id: UUID,
    environment: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Latency dashboard: p50/p90/p95/p99, average and max."""
    start, end = _resolve_time_range(start_time, end_time)
    service = ObservabilityService(db)
    return await service.get_latency(project_id, environment=environment, start_time=start, end_time=end)


_OBSERVABILITY_SETTING_KEYS = {
    "observability_mode",  # METADATA_ONLY | HASHED_CONTENT | FULL_CONTENT
    "retention_days",
    "sample_rate",
    "capture_errors",
    "capture_quality_signals",
    "error_bypass_sampling",
}


@router.get("/projects/{project_id}/observability/settings")
async def get_observability_settings(
    project_id: UUID,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Return the project's observability privacy/retention/sampling settings."""
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundError("Project not found.")
    settings = project.settings or {}
    return {
        "observability_mode": settings.get("observability_mode", "METADATA_ONLY"),
        "retention_days": settings.get("retention_days"),
        "sample_rate": float(settings.get("sample_rate", 1.0)),
        "capture_errors": settings.get("capture_errors", True),
        "capture_quality_signals": settings.get("capture_quality_signals", True),
        "error_bypass_sampling": settings.get("error_bypass_sampling", True),
    }


@router.put("/projects/{project_id}/observability/settings")
async def update_observability_settings(
    project_id: UUID,
    payload: dict,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update observability privacy/retention/sampling settings for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundError("Project not found.")

    from app.core.permissions import resolve_user_project_access, require_capability, CAP_MANAGE_PROJECTS
    role, _ = await resolve_user_project_access(db, user.id, project_id, project.organization_id)
    if role is None:
        raise ForbiddenError("You do not have access to this project.")
    require_capability(role, CAP_MANAGE_PROJECTS)

    settings = dict(project.settings or {})

    if "observability_mode" in payload:
        mode = payload["observability_mode"]
        if mode not in ("METADATA_ONLY", "HASHED_CONTENT", "FULL_CONTENT"):
            raise ValidationFailure("observability_mode must be METADATA_ONLY, HASHED_CONTENT, or FULL_CONTENT.")
        settings["observability_mode"] = mode

    if "retention_days" in payload:
        retention = payload["retention_days"]
        if retention is not None:
            try:
                retention = int(retention)
            except (TypeError, ValueError):
                raise ValidationFailure("retention_days must be an integer.")
            if retention <= 0:
                raise ValidationFailure("retention_days must be positive.")
        settings["retention_days"] = retention

    if "sample_rate" in payload:
        sample_rate = payload["sample_rate"]
        try:
            sample_rate = float(sample_rate)
        except (TypeError, ValueError):
            raise ValidationFailure("sample_rate must be a number between 0.0 and 1.0.")
        if not (0.0 <= sample_rate <= 1.0):
            raise ValidationFailure("sample_rate must be between 0.0 and 1.0.")
        settings["sample_rate"] = sample_rate

    for key in ("capture_errors", "capture_quality_signals", "error_bypass_sampling"):
        if key in payload:
            settings[key] = bool(payload[key])

    project.settings = settings

    # Audit the configuration update
    from app.repositories.audit import AuditRepository
    audit = AuditRepository(db)
    await audit.record(
        action="OBSERVABILITY_CONFIG_UPDATED",
        organization_id=project.organization_id,
        user_id=user.id,
        resource_type="project",
        resource_id=project_id,
        metadata={"project_id": str(project_id), "updates": {k: payload[k] for k in payload if k in _OBSERVABILITY_SETTING_KEYS}},
    )

    await db.commit()
    return {
        "observability_mode": settings.get("observability_mode", "METADATA_ONLY"),
        "retention_days": settings.get("retention_days"),
        "sample_rate": float(settings.get("sample_rate", 1.0)),
        "capture_errors": settings.get("capture_errors", True),
        "capture_quality_signals": settings.get("capture_quality_signals", True),
        "error_bypass_sampling": settings.get("error_bypass_sampling", True),
    }


@router.get("/projects/{project_id}/observability/traces")
async def list_traces(
    project_id: UUID,
    environment: str | None = Query(None),
    status: str | None = Query(None),
    model: str | None = Query(None),
    provider: str | None = Query(None),
    trace_id: str | None = Query(None),
    error_category: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """List paginated traces with filtering query capabilities."""
    start = datetime.fromisoformat(start_time) if start_time else None
    end = datetime.fromisoformat(end_time) if end_time else None

    service = ObservabilityService(db)
    return await service.get_traces_paginated(
        project_id,
        environment=environment,
        status=status,
        model=model,
        provider=provider,
        trace_id=trace_id,
        error_category=error_category,
        start_time=start,
        end_time=end,
        limit=limit,
        offset=offset,
    )


@router.get("/observability/traces/{trace_id}")
async def get_trace_details(
    trace_id: str,
    request: Request,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full trace duration details along with its sorted span hierarchy tree."""
    service = ObservabilityService(db)
    
    from app.repositories.project import ProjectRepository
    project_repo = ProjectRepository(db)
    
    from sqlalchemy import select
    from app.models.trace import Trace
    stmt = select(Trace).where(Trace.trace_id == trace_id)
    res = await db.execute(stmt)
    trace = res.scalar_one_or_none()
    
    if not trace:
        from app.core.errors import NotFoundError
        raise NotFoundError("Trace not found.")

    if hasattr(request.state, "is_service_token") and request.state.is_service_token:
        if trace.project_id != request.state.service_token_project_id:
            raise ForbiddenError("Service token project boundary mismatch.")
    else:
        project_obj = await project_repo.get_by_id(trace.project_id)
        if not project_obj:
            raise NotFoundError("Project not found.")
        
        from app.core.permissions import resolve_user_project_access
        role, _ = await resolve_user_project_access(
            session=db,
            user_id=user.id,
            project_id=trace.project_id,
            org_id=project_obj.organization_id,
        )
        if role is None:
            raise ForbiddenError("You do not have access to this project.")

    return await service.get_trace_detail(trace.project_id, trace_id)


@router.post("/projects/{project_id}/observability/quality-signals")
async def record_trace_quality_signals(
    project_id: UUID,
    payload: dict,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
    _role: Role = Depends(deps.require_project_capability("view_all")),
):
    """Submit quality signals and feed feedback parameters into trace metadata."""
    trace_id = payload.get("trace_id")
    signals = payload.get("signals")
    if not trace_id or not isinstance(signals, dict):
        raise ValidationFailure("Payload must contain trace_id and signals dictionary.")

    service = ObservabilityService(db)
    await service.record_quality_signals(project_id, trace_id, signals)
    return {"status": "recorded"}
