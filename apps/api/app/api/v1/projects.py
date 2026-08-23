"""Project endpoints (spec §35; AT-011..AT-014)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProjectService(session)
    project = await service.create(
        organization_id=organization_id, user_id=user.id, payload=payload
    )
    return ok(project)


@router.get("", status_code=status.HTTP_200_OK)
async def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProjectService(session)
    projects, total = await service.list(
        organization_id=organization_id, user_id=user.id, page=page, page_size=page_size
    )
    return ok_list(projects, page=page, page_size=page_size, total=total)


@router.get("/{project_id}", status_code=status.HTTP_200_OK)
async def get_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProjectService(session)
    project = await service.get(
        project_id=project_id, organization_id=organization_id, user_id=user.id
    )
    return ok(project)


@router.patch("/{project_id}", status_code=status.HTTP_200_OK)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProjectService(session)
    project = await service.update(
        project_id=project_id,
        organization_id=organization_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = ProjectService(session)
    await service.delete(project_id=project_id, organization_id=organization_id, user_id=user.id)
    response.status_code = status.HTTP_204_NO_CONTENT
