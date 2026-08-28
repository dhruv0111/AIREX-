"""Experiment endpoints (Phase 6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_active_organization, get_current_user
from app.core.errors import NotFoundError, ValidationFailure
from app.db.session import get_db
from app.models import User, Experiment, ExperimentRun
from app.schemas.common import ok, ok_list
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services.experiment import ExperimentService

router = APIRouter(tags=["experiments"])


# ------------------------------------------------------------- Project Scoped
@router.post("/projects/{project_id}/experiments", status_code=http_status.HTTP_201_CREATED)
async def create_experiment(
    project_id: UUID,
    payload: ExperimentCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if payload.project_id != project_id:
        raise ValidationFailure("Project ID in path does not match body.")
    service = ExperimentService(session)
    exp = await service.create(organization_id=organization_id, user_id=user.id, payload=payload)
    return ok(exp)


@router.get("/projects/{project_id}/experiments", status_code=http_status.HTTP_200_OK)
async def list_experiments(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ExperimentService(session)
    exps = await service.list_experiments(
        organization_id=organization_id, project_id=project_id, user_id=user.id
    )
    return ok(exps)


# ---------------------------------------------------------------- Experiment
@router.get("/experiments/{experiment_id}", status_code=http_status.HTTP_200_OK)
async def get_experiment(
    experiment_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ExperimentService(session)
    exp = await service.get(organization_id=organization_id, experiment_id=experiment_id, user_id=user.id)
    return ok(exp)


@router.patch("/experiments/{experiment_id}", status_code=http_status.HTTP_200_OK)
async def update_experiment(
    experiment_id: UUID,
    payload: ExperimentUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ExperimentService(session)
    # Check permission and existence
    exp = await service.get(organization_id=organization_id, experiment_id=experiment_id, user_id=user.id)
    
    # Reload model directly to update fields
    exp_model = await session.get(Experiment, experiment_id)
    if payload.name is not None:
        exp_model.name = payload.name
    if payload.description is not None:
        exp_model.description = payload.description
    
    await session.commit()
    return ok(await service.get(organization_id=organization_id, experiment_id=experiment_id, user_id=user.id))


@router.delete("/experiments/{experiment_id}", status_code=http_status.HTTP_200_OK)
async def delete_experiment(
    experiment_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ExperimentService(session)
    await service.delete_experiment(organization_id=organization_id, experiment_id=experiment_id, user_id=user.id)
    return ok({"deleted": True})


# ------------------------------------------------------------------ Execution
@router.post("/experiments/{experiment_id}/run", status_code=http_status.HTTP_200_OK)
async def run_experiment(
    experiment_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ExperimentService(session)
    run = await service.start_run(organization_id=organization_id, experiment_id=experiment_id, user_id=user.id)
    return ok(run)


@router.post("/experiments/{id}/cancel", status_code=http_status.HTTP_200_OK)
async def cancel_experiment_run(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # 'id' can represent experiment_id or run_id.
    service = ExperimentService(session)
    
    # Check if 'id' is a run_id
    run = await session.get(ExperimentRun, id)
    if run:
        res = await service.cancel_run(organization_id=organization_id, run_id=run.id, user_id=user.id)
        return ok(res)

    # Else it's an experiment_id: find active running run
    stmt = (
        select(ExperimentRun)
        .where(ExperimentRun.experiment_id == id, ExperimentRun.status.in_(["QUEUED", "RUNNING"]))
        .order_by(ExperimentRun.created_at.desc())
    )
    res_stmt = await session.execute(stmt)
    active_run = res_stmt.scalars().first()
    if not active_run:
        raise NotFoundError("No active running run found for the experiment.")

    res = await service.cancel_run(organization_id=organization_id, run_id=active_run.id, user_id=user.id)
    return ok(res)


# ----------------------------------------------------------------- Subresources
@router.get("/experiments/{experiment_id}/runs", status_code=http_status.HTTP_200_OK)
async def list_runs(
    experiment_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ExperimentService(session)
    runs = await service.list_runs(organization_id=organization_id, experiment_id=experiment_id, user_id=user.id)
    return ok(runs)


async def _resolve_run_id(id: UUID, session: AsyncSession) -> UUID:
    """Helper to resolve either a run_id or an experiment_id (getting its latest run)."""
    run = await session.get(ExperimentRun, id)
    if run:
        return run.id
    
    # Try finding latest run of this experiment
    stmt = select(ExperimentRun).where(ExperimentRun.experiment_id == id).order_by(ExperimentRun.created_at.desc())
    res = await session.execute(stmt)
    latest_run = res.scalars().first()
    if latest_run:
        return latest_run.id
    raise NotFoundError("No experiment run was found.")


@router.get("/experiments/{id}/results", status_code=http_status.HTTP_200_OK)
async def get_results(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    run_id = await _resolve_run_id(id, session)
    service = ExperimentService(session)
    comparisons = await service.get_comparisons(organization_id=organization_id, run_id=run_id, user_id=user.id)
    return ok(comparisons)


@router.get("/experiments/{id}/comparison", status_code=http_status.HTTP_200_OK)
async def get_comparison(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    run_id = await _resolve_run_id(id, session)
    service = ExperimentService(session)
    comparisons = await service.get_comparisons(organization_id=organization_id, run_id=run_id, user_id=user.id)
    return ok(comparisons)


@router.get("/experiments/{id}/regressions", status_code=http_status.HTTP_200_OK)
async def get_regressions(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    run_id = await _resolve_run_id(id, session)
    service = ExperimentService(session)
    regressions = await service.get_regressions(organization_id=organization_id, run_id=run_id, user_id=user.id)
    return ok(regressions)


@router.get("/experiments/{id}/quality-gates", status_code=http_status.HTTP_200_OK)
async def get_quality_gates(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    run_id = await _resolve_run_id(id, session)
    service = ExperimentService(session)
    gates = await service.get_gate_results(organization_id=organization_id, run_id=run_id, user_id=user.id)
    return ok(gates)
