"""Benchmark endpoints (Phase 9)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.db.session import get_db
from app.models import User
from app.models.project import Project
from app.core.permissions import Role
from app.core.errors import ForbiddenError, NotFoundError
from app.services.organization import OrganizationService
from app.repositories.benchmark import BenchmarkRepository
from app.schemas.common import ok, ok_list
from app.schemas.benchmark import (
    BenchmarkSuiteCreate,
    BenchmarkVersionCreate,
    BenchmarkRunCreate,
)
from app.services.benchmark import BenchmarkService

router = APIRouter(tags=["benchmarks"])


async def _verify_project_access(
    project_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    require_write: bool = False
) -> Project:
    project = await db.get(Project, project_id)
    if not project or project.organization_id != organization_id:
        raise NotFoundError("Project not found.")

    from app.core.permissions import resolve_user_project_access
    role, _ = await resolve_user_project_access(db, user_id, project_id, organization_id)
    if role is None:
        raise ForbiddenError("You do not have access to this project.")

    if require_write and role == Role.VIEWER:
        raise ForbiddenError("Viewer cannot perform write operations on benchmarks.")

    return project


async def _verify_suite_access(
    suite_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    require_write: bool = False
) -> Project:
    repo = BenchmarkRepository(db)
    suite = await repo.get_suite_by_id(suite_id)
    if not suite:
        raise NotFoundError("Benchmark suite not found.")
    
    return await _verify_project_access(suite.project_id, organization_id, user_id, db, require_write)


async def _verify_run_access(
    run_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    require_write: bool = False
) -> Project:
    repo = BenchmarkRepository(db)
    run = await repo.get_run_by_id(run_id)
    if not run:
        raise NotFoundError("Benchmark run not found.")
    
    return await _verify_suite_access(run.benchmark_suite_id, organization_id, user_id, db, require_write)


# ------------------------------------------------------------- Project Scoped
@router.post("/projects/{project_id}/benchmarks", status_code=http_status.HTTP_201_CREATED)
async def create_benchmark_suite(
    project_id: UUID,
    payload: BenchmarkSuiteCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = BenchmarkService(session)
    suite = await service.create_suite(
        organization_id=organization_id,
        user_id=user.id,
        project_id=project_id,
        payload=payload,
    )
    return ok(suite)


@router.get("/projects/{project_id}/benchmarks", status_code=http_status.HTTP_200_OK)
async def list_benchmark_suites(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = BenchmarkService(session)
    suites = await service.list_suites(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
    )
    return ok(suites)


# ---------------------------------------------------------------- Benchmark
@router.get("/benchmarks/{suite_id}", status_code=http_status.HTTP_200_OK)
async def get_benchmark_suite(
    suite_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_suite_access(suite_id, organization_id, user.id, session, require_write=False)
    service = BenchmarkService(session)
    suite = await service.get_suite(
        organization_id=organization_id,
        suite_id=suite_id,
        user_id=user.id,
    )
    return ok(suite)


@router.post("/benchmarks/{suite_id}/versions", status_code=http_status.HTTP_201_CREATED)
async def create_benchmark_version(
    suite_id: UUID,
    payload: BenchmarkVersionCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_suite_access(suite_id, organization_id, user.id, session, require_write=True)
    service = BenchmarkService(session)
    version = await service.create_version(
        organization_id=organization_id,
        suite_id=suite_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(version)


@router.get("/benchmarks/{suite_id}/versions", status_code=http_status.HTTP_200_OK)
async def list_benchmark_versions(
    suite_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_suite_access(suite_id, organization_id, user.id, session, require_write=False)
    service = BenchmarkService(session)
    versions = await service.list_versions(
        organization_id=organization_id,
        suite_id=suite_id,
        user_id=user.id,
    )
    return ok(versions)


@router.post("/benchmarks/{suite_id}/runs", status_code=http_status.HTTP_201_CREATED)
async def trigger_benchmark_run(
    suite_id: UUID,
    payload: BenchmarkRunCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_suite_access(suite_id, organization_id, user.id, session, require_write=True)
    service = BenchmarkService(session)
    run = await service.trigger_run(
        organization_id=organization_id,
        suite_id=suite_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(run)


@router.get("/benchmarks/{suite_id}/runs", status_code=http_status.HTTP_200_OK)
async def list_benchmark_runs(
    suite_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_suite_access(suite_id, organization_id, user.id, session, require_write=False)
    service = BenchmarkService(session)
    runs = await service.list_runs(
        organization_id=organization_id,
        suite_id=suite_id,
        user_id=user.id,
    )
    return ok(runs)


@router.get("/benchmarks/runs/{run_id}", status_code=http_status.HTTP_200_OK)
async def get_benchmark_run_detail(
    run_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_run_access(run_id, organization_id, user.id, session, require_write=False)
    service = BenchmarkService(session)
    detail = await service.get_run_detail(
        organization_id=organization_id,
        run_id=run_id,
        user_id=user.id,
    )
    return ok(detail)
