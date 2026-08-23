"""Organization endpoints (spec §34; AT-009/010) + member management (spec §36–§38)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.member import MemberAddRequest, MemberRoleUpdate
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
)
from app.services.member import MemberService
from app.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = OrganizationService(session)
    org = await service.create(actor_user_id=user.id, payload=payload)
    return ok(org)


@router.get("", status_code=status.HTTP_200_OK)
async def list_organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = OrganizationService(session)
    orgs = await service.list_for_user(user.id)
    return ok_list(orgs, page=1, page_size=len(orgs) or 1, total=len(orgs))


@router.get("/{organization_id}", status_code=status.HTTP_200_OK)
async def get_organization(
    organization_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = OrganizationService(session)
    org = await service.get_for_user(organization_id, user.id)
    return ok(org)


@router.patch("/{organization_id}", status_code=status.HTTP_200_OK)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = OrganizationService(session)
    org = await service.update(organization_id, user.id, payload)
    return ok(org)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    organization_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = OrganizationService(session)
    await service.delete(organization_id, user.id)
    response.status_code = status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------
@router.get("/{organization_id}/members", status_code=status.HTTP_200_OK)
async def list_members(
    organization_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = MemberService(session)
    members = await service.list(organization_id=organization_id, user_id=user.id)
    return ok_list(members, page=1, page_size=len(members) or 1, total=len(members))


@router.post("/{organization_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    organization_id: UUID,
    payload: MemberAddRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = MemberService(session)
    member = await service.add(organization_id=organization_id, actor_id=user.id, payload=payload)
    return ok(member)


@router.patch("/{organization_id}/members/{member_id}", status_code=status.HTTP_200_OK)
async def change_member_role(
    organization_id: UUID,
    member_id: UUID,
    payload: MemberRoleUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = MemberService(session)
    member = await service.change_role(
        organization_id=organization_id, member_id=member_id, actor_id=user.id, payload=payload
    )
    return ok(member)


@router.delete("/{organization_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: UUID,
    member_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = MemberService(session)
    await service.remove(organization_id=organization_id, member_id=member_id, actor_id=user.id)
    response.status_code = status.HTTP_204_NO_CONTENT
