"""Organization service (spec §34; AT-009/010)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import CAP_MANAGE_ORGANIZATION, Role, require_capability
from app.repositories.audit import AuditRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)


class OrganizationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._orgs = OrganizationRepository(session)
        self._users = UserRepository(session)
        self._audit = AuditRepository(session)

    async def create(
        self, *, actor_user_id: UUID, payload: OrganizationCreate
    ) -> OrganizationResponse:
        assert payload.slug is not None  # model_validator guarantees a slug
        existing = await self._orgs.get_by_slug(payload.slug)
        if existing:
            raise ConflictError("An organization with this slug already exists.")
        try:
            org = await self._orgs.create(name=payload.name, slug=payload.slug)
        except IntegrityError:
            raise ConflictError("An organization with this slug already exists.")
        # Creator becomes OWNER (AT-009).
        await self._orgs.add_member(organization_id=org.id, user_id=actor_user_id, role=Role.OWNER)
        await self._audit.record(
            action="organization.created",
            organization_id=org.id,
            user_id=actor_user_id,
            resource_type="organization",
            resource_id=org.id,
        )
        await self._session.commit()
        return OrganizationResponse.model_validate(org, from_attributes=True)

    async def list_for_user(self, user_id: UUID) -> list[OrganizationResponse]:
        orgs = await self._orgs.list_organizations(user_id)
        return [OrganizationResponse.model_validate(o, from_attributes=True) for o in orgs]

    async def get_for_user(self, org_id: UUID, user_id: UUID) -> OrganizationResponse:
        membership = await self._orgs.get_membership(organization_id=org_id, user_id=user_id)
        if membership is None:
            raise NotFoundError("Organization was not found.")  # AT-010: hidden
        org = await self._orgs.get_by_id(org_id)
        if org is None:
            raise NotFoundError("Organization was not found.")
        return OrganizationResponse.model_validate(org, from_attributes=True)

    async def update(
        self, org_id: UUID, user_id: UUID, payload: OrganizationUpdate
    ) -> OrganizationResponse:
        await self._member_with_capability(org_id, user_id, CAP_MANAGE_ORGANIZATION)
        org = await self._orgs.get_by_id(org_id)
        if org is None:
            raise NotFoundError("Organization was not found.")
        if payload.name is not None:
            org.name = payload.name
        await self._audit.record(
            action="organization.updated",
            organization_id=org_id,
            user_id=user_id,
            resource_type="organization",
            resource_id=org_id,
        )
        await self._session.commit()
        return OrganizationResponse.model_validate(org, from_attributes=True)

    async def delete(self, org_id: UUID, user_id: UUID) -> None:
        await self._member_with_capability(org_id, user_id, CAP_MANAGE_ORGANIZATION)
        org = await self._orgs.get_by_id(org_id)
        if org is None:
            raise NotFoundError("Organization was not found.")
        await self._audit.record(
            action="organization.deleted",
            organization_id=org_id,
            user_id=user_id,
            resource_type="organization",
            resource_id=org_id,
        )
        await self._session.delete(org)
        await self._session.commit()

    async def resolve_membership(self, org_id: UUID, user_id: UUID) -> Role | None:
        membership = await self._orgs.get_membership(organization_id=org_id, user_id=user_id)
        if membership is None:
            return None
        try:
            return Role(membership.role)
        except ValueError:
            return None

    async def _member_with_capability(self, org_id: UUID, user_id: UUID, capability: str) -> Role:
        role = await self.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role
