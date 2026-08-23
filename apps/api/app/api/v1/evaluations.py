"""Evaluation endpoints (Phase 3 §24–§29, §40, §43)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.errors import ValidationFailure
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.evaluation import EvaluationCreate
from app.services.evaluation import EvaluationService

router = APIRouter(tags=["evaluations"])


@router.post("/evaluations", status_code=http_status.HTTP_201_CREATED)
async def create_evaluation(
    payload: EvaluationCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EvaluationService(session)
    run = await service.create(organization_id=organization_id, user_id=user.id, payload=payload)
    return ok(run)


@router.post("/evaluations/{evaluation_id}/run", status_code=http_status.HTTP_200_OK)
async def run_evaluation(
    evaluation_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EvaluationService(session)
    run = await service.start(
        organization_id=organization_id, run_id=evaluation_id, user_id=user.id
    )
    return ok(run)


@router.get("/evaluations", status_code=http_status.HTTP_200_OK)
async def list_evaluations(
    project_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    model_id: UUID | None = None,
    dataset_version_id: UUID | None = None,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if page < 1 or page_size < 1:
        raise ValidationFailure("page and page_size must be positive.")
    service = EvaluationService(session)
    runs, total = await service.list_runs(
        organization_id=organization_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        project_id=project_id,
        status=status,
        model_id=model_id,
        dataset_version_id=dataset_version_id,
    )
    return ok_list(runs, page=page, page_size=page_size, total=total)


@router.get("/evaluations/{evaluation_id}", status_code=http_status.HTTP_200_OK)
async def get_evaluation(
    evaluation_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EvaluationService(session)
    run = await service.get(organization_id=organization_id, run_id=evaluation_id, user_id=user.id)
    return ok(run)


@router.get("/evaluations/{evaluation_id}/results", status_code=http_status.HTTP_200_OK)
async def list_results(
    evaluation_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    failure_type: str | None = None,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if page < 1 or page_size < 1:
        raise ValidationFailure("page and page_size must be positive.")
    service = EvaluationService(session)
    results, total = await service.results(
        organization_id=organization_id,
        run_id=evaluation_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        failure_type=failure_type,
    )
    return ok_list(results, page=page, page_size=page_size, total=total)


@router.post("/evaluations/{evaluation_id}/cancel", status_code=http_status.HTTP_200_OK)
async def cancel_evaluation(
    evaluation_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EvaluationService(session)
    run = await service.cancel(
        organization_id=organization_id, run_id=evaluation_id, user_id=user.id
    )
    return ok(run)


@router.patch(
    "/evaluations/{evaluation_id}/results/{result_id}", status_code=http_status.HTTP_409_CONFLICT
)
async def patch_result(
    evaluation_id: UUID,
    result_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    # Evaluation results are immutable (Phase 3 §43, AT-P3-027).
    service = EvaluationService(session)
    await service.reject_result_mutation(
        organization_id=organization_id, run_id=evaluation_id, user_id=user.id
    )
