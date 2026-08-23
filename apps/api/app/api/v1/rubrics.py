"""Rubric endpoints (Phase 4 §22, §48)."""

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
from app.schemas.rubric import RubricCreate, RubricUpdate
from app.services.rubric import RubricService

router = APIRouter(tags=["rubrics"])


@router.post("/rubrics", status_code=http_status.HTTP_201_CREATED)
async def create_rubric(
    payload: RubricCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = RubricService(session)
    rubric = await service.create(
        organization_id=organization_id,
        project_id=payload.project_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(rubric)


@router.get("/rubrics", status_code=http_status.HTTP_200_OK)
async def list_rubrics(
    project_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if page < 1 or page_size < 1:
        raise ValidationFailure("page and page_size must be positive.")
    service = RubricService(session)
    rubrics, total = await service.list(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
    )
    return ok_list(rubrics, page=page, page_size=page_size, total=total)


@router.get("/rubrics/{rubric_id}", status_code=http_status.HTTP_200_OK)
async def get_rubric(
    rubric_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = RubricService(session)
    rubric = await service.get(
        organization_id=organization_id, rubric_id=rubric_id, user_id=user.id
    )
    return ok(rubric)


@router.patch("/rubrics/{rubric_id}", status_code=http_status.HTTP_200_OK)
async def update_rubric(
    rubric_id: UUID,
    payload: RubricUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = RubricService(session)
    rubric = await service.update(
        organization_id=organization_id, rubric_id=rubric_id, user_id=user.id, payload=payload
    )
    return ok(rubric)


@router.delete("/rubrics/{rubric_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def archive_rubric(
    rubric_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    # Safe archive (ADR-019); historical evaluations keep referencing their version.
    service = RubricService(session)
    await service.archive(organization_id=organization_id, rubric_id=rubric_id, user_id=user.id)
