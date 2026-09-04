"""Enterprise Team Management and Project Access Service (Phase 13)."""

from __future__ import annotations

import re
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationFailure
from app.core.permissions import resolve_user_project_access
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.team import Team, TeamMember, TeamProjectAccess, UserProjectAccess
from app.models.user import User
from app.repositories.audit import AuditRepository


class TeamService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    # ---------------------------------------------------------
    # Team CRUD
    # ---------------------------------------------------------
    async def create_team(self, org_id: UUID, user_id: UUID, name: str, description: str | None = None) -> Team:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not slug:
            slug = "team"

        # Check slug uniqueness within org
        stmt = select(Team).where(and_(Team.organization_id == org_id, Team.slug == slug))
        res = await self.session.execute(stmt)
        if res.scalars().first():
            raise ConflictError(f"Team with name/slug '{name}' already exists.")

        team = Team(
            organization_id=org_id,
            name=name,
            slug=slug,
            description=description,
        )
        self.session.add(team)
        await self.session.flush()

        # Add creator as team LEAD
        member = TeamMember(
            team_id=team.id,
            user_id=user_id,
            role="LEAD",
            created_at=datetime.now(UTC),
        )
        self.session.add(member)
        await self.session.flush()

        await self.audit.record(
            action="team.created",
            organization_id=org_id,
            user_id=user_id,
            resource_type="team",
            resource_id=team.id,
            metadata={"name": team.name, "slug": team.slug},
        )
        await self.session.commit()
        await self.session.refresh(team)
        return team

    async def list_teams(self, org_id: UUID) -> list[Team]:
        stmt = select(Team).where(Team.organization_id == org_id).order_by(Team.name)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_team(self, org_id: UUID, team_id: UUID) -> Team:
        stmt = select(Team).where(and_(Team.organization_id == org_id, Team.id == team_id))
        res = await self.session.execute(stmt)
        team = res.scalars().first()
        if not team:
            raise NotFoundError("Team not found.")
        return team

    async def update_team(self, org_id: UUID, team_id: UUID, user_id: UUID, data: dict) -> Team:
        team = await self.get_team(org_id, team_id)
        if "name" in data and data["name"]:
            team.name = data["name"]
        if "description" in data:
            team.description = data["description"]

        await self.audit.record(
            action="team.updated",
            organization_id=org_id,
            user_id=user_id,
            resource_type="team",
            resource_id=team.id,
            metadata=data,
        )
        await self.session.commit()
        await self.session.refresh(team)
        return team

    async def delete_team(self, org_id: UUID, team_id: UUID, user_id: UUID) -> None:
        team = await self.get_team(org_id, team_id)
        name = team.name
        await self.session.delete(team)
        await self.audit.record(
            action="team.deleted",
            organization_id=org_id,
            user_id=user_id,
            resource_type="team",
            resource_id=team_id,
            metadata={"name": name},
        )
        await self.session.commit()

    # ---------------------------------------------------------
    # Team Membership
    # ---------------------------------------------------------
    async def add_member(self, org_id: UUID, team_id: UUID, admin_id: UUID, target_user_id: UUID, role: str = "MEMBER") -> TeamMember:
        team = await self.get_team(org_id, team_id)

        # Target user must be a member of the organization
        stmt_org_mem = select(OrganizationMember).where(
            and_(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == target_user_id)
        )
        res_org_mem = await self.session.execute(stmt_org_mem)
        if not res_org_mem.scalars().first():
            raise ValidationFailure("User must be a member of the organization before joining a team.")

        # Check existing team membership
        stmt = select(TeamMember).where(and_(TeamMember.team_id == team_id, TeamMember.user_id == target_user_id))
        res = await self.session.execute(stmt)
        if res.scalars().first():
            raise ConflictError("User is already a member of this team.")

        member = TeamMember(
            team_id=team_id,
            user_id=target_user_id,
            role=role if role in ("LEAD", "MEMBER") else "MEMBER",
            created_at=datetime.now(UTC),
        )
        self.session.add(member)
        await self.session.flush()

        await self.audit.record(
            action="team.member_added",
            organization_id=org_id,
            user_id=admin_id,
            resource_type="team_member",
            resource_id=member.id,
            metadata={"team_id": str(team_id), "target_user_id": str(target_user_id), "role": member.role},
        )
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def remove_member(self, org_id: UUID, team_id: UUID, admin_id: UUID, target_user_id: UUID) -> None:
        team = await self.get_team(org_id, team_id)
        stmt = select(TeamMember).where(and_(TeamMember.team_id == team_id, TeamMember.user_id == target_user_id))
        res = await self.session.execute(stmt)
        member = res.scalars().first()
        if not member:
            raise NotFoundError("Team member not found.")

        await self.session.delete(member)
        await self.audit.record(
            action="team.member_removed",
            organization_id=org_id,
            user_id=admin_id,
            resource_type="team_member",
            resource_id=member.id,
            metadata={"team_id": str(team_id), "target_user_id": str(target_user_id)},
        )
        await self.session.commit()

    async def list_members(self, org_id: UUID, team_id: UUID) -> list[dict]:
        await self.get_team(org_id, team_id)
        stmt = select(TeamMember, User).join(User, User.id == TeamMember.user_id).where(TeamMember.team_id == team_id)
        res = await self.session.execute(stmt)
        rows = res.all()
        results = []
        for member, user in rows:
            results.append({
                "id": member.id,
                "team_id": member.team_id,
                "user_id": member.user_id,
                "role": member.role,
                "user_email": user.email,
                "user_name": user.name,
                "created_at": member.created_at,
            })
        return results

    # ---------------------------------------------------------
    # Team Project Access
    # ---------------------------------------------------------
    async def assign_team_project_access(
        self, org_id: UUID, team_id: UUID, user_id: UUID, project_id: UUID, permission_role: str = "ENGINEER"
    ) -> TeamProjectAccess:
        team = await self.get_team(org_id, team_id)

        # Validate project belongs to org
        project = await self.session.get(Project, project_id)
        if not project or project.organization_id != org_id:
            raise NotFoundError("Project not found in this organization.")

        stmt = select(TeamProjectAccess).where(
            and_(TeamProjectAccess.team_id == team_id, TeamProjectAccess.project_id == project_id)
        )
        res = await self.session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            existing.permission_role = permission_role
            access = existing
        else:
            access = TeamProjectAccess(
                team_id=team_id,
                project_id=project_id,
                permission_role=permission_role,
                created_at=datetime.now(UTC),
            )
            self.session.add(access)

        await self.session.flush()
        await self.audit.record(
            action="team.project_access_assigned",
            organization_id=org_id,
            user_id=user_id,
            resource_type="team_project_access",
            resource_id=access.id,
            metadata={"team_id": str(team_id), "project_id": str(project_id), "role": permission_role},
        )
        await self.session.commit()
        await self.session.refresh(access)
        return access

    async def remove_team_project_access(self, org_id: UUID, team_id: UUID, user_id: UUID, project_id: UUID) -> None:
        await self.get_team(org_id, team_id)
        stmt = select(TeamProjectAccess).where(
            and_(TeamProjectAccess.team_id == team_id, TeamProjectAccess.project_id == project_id)
        )
        res = await self.session.execute(stmt)
        access = res.scalars().first()
        if not access:
            raise NotFoundError("Team project access not found.")

        await self.session.delete(access)
        await self.audit.record(
            action="team.project_access_removed",
            organization_id=org_id,
            user_id=user_id,
            resource_type="team_project_access",
            resource_id=access.id,
            metadata={"team_id": str(team_id), "project_id": str(project_id)},
        )
        await self.session.commit()

    async def list_team_project_access(self, org_id: UUID, team_id: UUID) -> list[dict]:
        await self.get_team(org_id, team_id)
        stmt = (
            select(TeamProjectAccess, Project)
            .join(Project, Project.id == TeamProjectAccess.project_id)
            .where(TeamProjectAccess.team_id == team_id)
        )
        res = await self.session.execute(stmt)
        results = []
        for access, project in res.all():
            results.append({
                "id": access.id,
                "team_id": access.team_id,
                "project_id": access.project_id,
                "permission_role": access.permission_role,
                "project_name": project.name,
                "created_at": access.created_at,
            })
        return results

    # ---------------------------------------------------------
    # Direct User Project Access & Access Resolution
    # ---------------------------------------------------------
    async def assign_user_project_access(
        self, org_id: UUID, project_id: UUID, admin_id: UUID, target_user_id: UUID, permission_role: str = "ENGINEER"
    ) -> UserProjectAccess:
        project = await self.session.get(Project, project_id)
        if not project or project.organization_id != org_id:
            raise NotFoundError("Project not found in this organization.")

        stmt = select(UserProjectAccess).where(
            and_(UserProjectAccess.user_id == target_user_id, UserProjectAccess.project_id == project_id)
        )
        res = await self.session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            existing.permission_role = permission_role
            access = existing
        else:
            access = UserProjectAccess(
                user_id=target_user_id,
                project_id=project_id,
                permission_role=permission_role,
                created_at=datetime.now(UTC),
            )
            self.session.add(access)

        await self.session.flush()
        await self.audit.record(
            action="user.project_access_assigned",
            organization_id=org_id,
            user_id=admin_id,
            resource_type="user_project_access",
            resource_id=access.id,
            metadata={"target_user_id": str(target_user_id), "project_id": str(project_id), "role": permission_role},
        )
        await self.session.commit()
        await self.session.refresh(access)
        return access

    async def resolve_access(self, org_id: UUID, user_id: UUID, project_id: UUID) -> dict:
        role, access_type = await resolve_user_project_access(self.session, user_id, project_id, org_id)
        return {
            "user_id": user_id,
            "project_id": project_id,
            "effective_role": role.value if role else None,
            "access_type": access_type,
        }
