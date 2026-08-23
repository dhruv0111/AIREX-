"""Organization member management (spec §36–§39; AT-P1-019..025)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import CAP_MANAGE_MEMBERS, Role, require_capability
from app.repositories.audit import AuditRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.schemas.member import MemberAddRequest, MemberResponse, MemberRoleUpdate
from app.services.organization import OrganizationService


class MemberService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._orgs = OrganizationRepository(session)
        self._users = UserRepository(session)
        self._audit = AuditRepository(session)
        self._org_service = OrganizationService(session)

    async def _actor_role(self, org_id: UUID, user_id: UUID) -> Role:
        role = await self._org_service.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, CAP_MANAGE_MEMBERS)
        return role

    async def list(self, *, organization_id: UUID, user_id: UUID) -> list[MemberResponse]:
        role = await self._org_service.resolve_membership(organization_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        members = await self._orgs.list_members(organization_id)
        result: list[MemberResponse] = []
        for member, user in members:
            result.append(
                MemberResponse(
                    membership_id=member.id,
                    user_id=member.user_id,
                    email=getattr(user, "email", None),
                    name=getattr(user, "name", None),
                    role=member.role,
                    joined_at=member.created_at,
                )
            )
        return result

    async def add(
        self, *, organization_id: UUID, actor_id: UUID, payload: MemberAddRequest
    ) -> MemberResponse:
        await self._actor_role(organization_id, actor_id)
        user = await self._users.get_by_email(payload.email.strip().lower())
        if user is None:
            raise NotFoundError("No user with this email exists.")
        existing = await self._orgs.get_membership(organization_id=organization_id, user_id=user.id)
        if existing is not None:
            raise ConflictError("This user is already a member of the organization.")
        member = await self._orgs.add_member(
            organization_id=organization_id, user_id=user.id, role=Role(payload.role)
        )
        await self._audit.record(
            action="MEMBER_ADDED",
            organization_id=organization_id,
            user_id=actor_id,
            resource_type="organization_member",
            resource_id=member.id,
            metadata={"role": payload.role},
        )
        await self._session.commit()
        return MemberResponse(
            membership_id=member.id,
            user_id=member.user_id,
            email=user.email,
            name=user.name,
            role=member.role,
            joined_at=member.created_at,
        )

    async def change_role(
        self,
        *,
        organization_id: UUID,
        member_id: UUID,
        actor_id: UUID,
        payload: MemberRoleUpdate,
    ) -> MemberResponse:
        actor_role = await self._actor_role(organization_id, actor_id)
        member = await self._orgs.get_member_by_id(member_id)
        if member is None or member.organization_id != organization_id:
            raise NotFoundError("Member was not found.")
        target_role = Role(member.role)

        # ADMIN cannot manage OWNER members (spec §37).
        if actor_role == Role.ADMIN and target_role == Role.OWNER:
            raise ForbiddenError("An ADMIN cannot change the organization owner's role.")
        if actor_role == Role.ADMIN and Role(payload.role) == Role.OWNER:
            raise ForbiddenError("Only an OWNER can grant the OWNER role.")

        # Owner safety: cannot demote the final owner (spec §38).
        if (
            target_role == Role.OWNER
            and Role(payload.role) != Role.OWNER
            and await self._orgs.count_owners(organization_id) <= 1
        ):
            raise ConflictError("The organization must keep at least one owner.")

        member.role = payload.role
        await self._audit.record(
            action="MEMBER_ROLE_CHANGED",
            organization_id=organization_id,
            user_id=actor_id,
            resource_type="organization_member",
            resource_id=member.id,
            metadata={"from": target_role.value, "to": payload.role},
        )
        await self._session.commit()
        user = await self._users.get_by_id(member.user_id)
        return MemberResponse(
            membership_id=member.id,
            user_id=member.user_id,
            email=user.email if user else None,
            name=user.name if user else None,
            role=member.role,
            joined_at=member.created_at,
        )

    async def remove(self, *, organization_id: UUID, member_id: UUID, actor_id: UUID) -> None:
        actor_role = await self._actor_role(organization_id, actor_id)
        member = await self._orgs.get_member_by_id(member_id)
        if member is None or member.organization_id != organization_id:
            raise NotFoundError("Member was not found.")
        target_role = Role(member.role)

        if target_role == Role.OWNER:
            if actor_role != Role.OWNER:
                raise ForbiddenError("Only an OWNER can remove the organization owner.")
            if await self._orgs.count_owners(organization_id) <= 1:
                raise ConflictError("The organization must keep at least one owner.")
        await self._audit.record(
            action="MEMBER_REMOVED",
            organization_id=organization_id,
            user_id=actor_id,
            resource_type="organization_member",
            resource_id=member.id,
        )
        await self._orgs.remove_member(member)
        await self._session.commit()
