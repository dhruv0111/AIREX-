"""Provider endpoints (spec §20–§22; AT-P1-001..006, 026..028)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.provider import (
    ProviderCreate,
    ProviderRotateRequest,
    ProviderUpdate,
)
from app.services.provider import ProviderService

router = APIRouter(prefix="/providers", tags=["providers"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProviderService(session)
    provider = await service.create(
        organization_id=organization_id, user_id=user.id, payload=payload
    )
    return ok(provider)


@router.get("", status_code=status.HTTP_200_OK)
async def list_providers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    provider_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProviderService(session)
    providers, total = await service.list(
        organization_id=organization_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        provider_type=provider_type,
        status=status_filter,
    )
    return ok_list(providers, page=page, page_size=page_size, total=total)


@router.get("/{provider_id}", status_code=status.HTTP_200_OK)
async def get_provider(
    provider_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProviderService(session)
    provider = await service.get(
        organization_id=organization_id, provider_id=provider_id, user_id=user.id
    )
    return ok(provider)


@router.patch("/{provider_id}", status_code=status.HTTP_200_OK)
async def update_provider(
    provider_id: UUID,
    payload: ProviderUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProviderService(session)
    provider = await service.update(
        organization_id=organization_id,
        provider_id=provider_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(provider)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = ProviderService(session)
    await service.delete(organization_id=organization_id, provider_id=provider_id, user_id=user.id)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.post("/{provider_id}/test", status_code=status.HTTP_200_OK)
async def test_provider(
    provider_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    check_rate_limit(f"provider_test:{user.id}", 30, 60)
    service = ProviderService(session)
    result = await service.test(
        organization_id=organization_id, provider_id=provider_id, user_id=user.id
    )
    return ok(result)


@router.post("/{provider_id}/rotate", status_code=status.HTTP_200_OK)
async def rotate_provider(
    provider_id: UUID,
    payload: ProviderRotateRequest,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = ProviderService(session)
    provider = await service.rotate(
        organization_id=organization_id,
        provider_id=provider_id,
        user_id=user.id,
        new_api_key=payload.api_key,
    )
    return ok(provider)
