"""Model endpoints (spec §23–§31; AT-P1-007..015, 029)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.provider import (
    ModelCreate,
    ModelInvokeRequest,
    ModelUpdate,
)
from app.services.model import ModelService

router = APIRouter(tags=["models"])


@router.post("/projects/{project_id}/models", status_code=status.HTTP_201_CREATED)
async def create_model(
    project_id: UUID,
    payload: ModelCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ModelService(session)
    model = await service.create(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(model)


@router.get("/projects/{project_id}/models", status_code=status.HTTP_200_OK)
async def list_models(
    project_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    provider: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ModelService(session)
    models, total = await service.list(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status_filter,
        provider=provider,
    )
    return ok_list(models, page=page, page_size=page_size, total=total)


@router.get("/models/{model_id}", status_code=status.HTTP_200_OK)
async def get_model(
    model_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ModelService(session)
    model = await service.get(organization_id=organization_id, model_id=model_id, user_id=user.id)
    return ok(model)


@router.patch("/models/{model_id}", status_code=status.HTTP_200_OK)
async def update_model(
    model_id: UUID,
    payload: ModelUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ModelService(session)
    model = await service.update(
        organization_id=organization_id, model_id=model_id, user_id=user.id, payload=payload
    )
    return ok(model)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = ModelService(session)
    await service.delete(organization_id=organization_id, model_id=model_id, user_id=user.id)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.post("/models/{model_id}/test", status_code=status.HTTP_200_OK)
async def test_model(
    model_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    check_rate_limit(f"model_test:{user.id}", 30, 60)
    service = ModelService(session)
    result = await service.test(organization_id=organization_id, model_id=model_id, user_id=user.id)
    return ok(result)


@router.post("/models/{model_id}/invoke", status_code=status.HTTP_200_OK)
async def invoke_model(
    model_id: UUID,
    payload: ModelInvokeRequest,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    check_rate_limit(f"model_invoke:{user.id}:{model_id}", 60, 60)
    service = ModelService(session)
    result = await service.invoke(
        organization_id=organization_id,
        model_id=model_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(result)


@router.get("/models/{model_id}/health", status_code=status.HTTP_200_OK)
async def model_health(
    model_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ModelService(session)
    health = await service.health(
        organization_id=organization_id, model_id=model_id, user_id=user.id
    )
    return ok(health)
