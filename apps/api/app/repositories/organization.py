"""Organization and membership repository (tenant-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.models import Organization, OrganizationMember


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._session.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none()

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        return await self._session.get(Organization, org_id)

    async def create(self, *, name: str, slug: str) -> Organization:
        org = Organization(name=name, slug=slug)
        self._session.add(org)
        await self._session.flush()
        return org

    async def add_member(
        self, *, organization_id: UUID, user_id: UUID, role: Role
    ) -> OrganizationMember:
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role=str(role),
            created_at=datetime.now(UTC),
        )
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_membership(
        self, *, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        result = await self._session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_memberships(self, user_id: UUID) -> list[OrganizationMember]:
        result = await self._session.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def list_members(self, organization_id: UUID) -> list[tuple[OrganizationMember, object]]:
        """Return (member, user) pairs for an organization's members."""
        from app.models import User

        result = await self._session.execute(
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.created_at)
        )
        return [(m, u) for m, u in result.all()]

    async def count_owners(self, organization_id: UUID) -> int:
        from app.core.permissions import Role

        result = await self._session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == Role.OWNER.value,
            )
        )
        return len(result.scalars().all())

    async def get_member_by_id(self, member_id: UUID) -> OrganizationMember | None:
        return await self._session.get(OrganizationMember, member_id)

    async def remove_member(self, member: OrganizationMember) -> None:
        await self._session.delete(member)

    async def list_organizations(self, user_id: UUID) -> list[Organization]:
        result = await self._session.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.created_at.desc())
        )
        return list(result.scalars().all())
