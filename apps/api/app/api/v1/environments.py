"""Environment endpoints (spec §32–§35; AT-P1-016..018)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.environment import (
    EnvironmentCreate,
    EnvironmentUpdate,
)
from app.services.environment import EnvironmentService

router = APIRouter(tags=["environments"])


@router.post("/projects/{project_id}/environments", status_code=status.HTTP_201_CREATED)
async def create_environment(
    project_id: UUID,
    payload: EnvironmentCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EnvironmentService(session)
    env = await service.create(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(env)


@router.get("/projects/{project_id}/environments", status_code=status.HTTP_200_OK)
async def list_environments(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EnvironmentService(session)
    envs = await service.list(
        organization_id=organization_id, project_id=project_id, user_id=user.id
    )
    return ok_list(envs, page=1, page_size=len(envs) or 1, total=len(envs))


@router.get("/environments/{environment_id}", status_code=status.HTTP_200_OK)
async def get_environment(
    environment_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EnvironmentService(session)
    env = await service.get(
        organization_id=organization_id, environment_id=environment_id, user_id=user.id
    )
    return ok(env)


@router.patch("/environments/{environment_id}", status_code=status.HTTP_200_OK)
async def update_environment(
    environment_id: UUID,
    payload: EnvironmentUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = EnvironmentService(session)
    env = await service.update(
        organization_id=organization_id,
        environment_id=environment_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(env)


@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    environment_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = EnvironmentService(session)
    await service.delete(
        organization_id=organization_id, environment_id=environment_id, user_id=user.id
    )
    response.status_code = status.HTTP_204_NO_CONTENT
