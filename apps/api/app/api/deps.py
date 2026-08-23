"""API dependencies: authentication and organization resolution (spec §40–§41)."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, ForbiddenError, ValidationFailure
from app.core.logging import organization_id_ctx, user_id_ctx
from app.db.session import get_db
from app.models import User
from app.services.auth import AuthService
from app.services.organization import OrganizationService

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthError("Authentication required.")
    service = AuthService(session)
    user = await service.user_from_token(credentials.credentials)
    user_id_ctx.set(str(user.id))
    return user


async def get_active_organization(
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UUID:
    """Resolve the active organization from the header, validated by membership.

    A user must never gain access merely by changing the header (spec §41):
    membership is always validated server-side.
    """
    org_service = OrganizationService(session)
    if x_organization_id:
        try:
            org_id = UUID(x_organization_id)
        except ValueError:
            raise ValidationFailure("X-Organization-Id is not a valid UUID.")
        membership = await org_service.resolve_membership(org_id, user.id)
        if membership is None:
            raise ForbiddenError("You do not have access to this organization.")
        organization_id_ctx.set(str(org_id))
        return org_id

    memberships = await org_service.list_for_user(user.id)
    if not memberships:
        raise ForbiddenError("You do not belong to any organization.")
    if len(memberships) > 1:
        raise ValidationFailure("Multiple organizations found. Set the X-Organization-Id header.")
    organization_id_ctx.set(str(memberships[0].id))
    return memberships[0].id
