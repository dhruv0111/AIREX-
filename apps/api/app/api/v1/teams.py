"""REST API endpoints for Organization Teams and Project Access (Phase 13)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.permissions import (
    Role,
    require_capability,
    CAP_MANAGE_TEAMS,
    CAP_VIEW_TEAMS,
    CAP_MANAGE_PROJECTS,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.team import (
    AccessResolutionResponse,
    TeamCreate,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamProjectAccessCreate,
    TeamProjectAccessResponse,
    TeamResponse,
    TeamUpdate,
    UserProjectAccessCreate,
    UserProjectAccessResponse,
)
from app.services.organization import OrganizationService
from app.services.team_service import TeamService

router = APIRouter(tags=["teams"])


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> TeamResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_TEAMS)

    service = TeamService(session)
    team = await service.create_team(org_id, user.id, payload.name, payload.description)
    return TeamResponse.model_validate(team)


@router.get("/teams", response_model=list[TeamResponse])
async def list_teams(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[TeamResponse]:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_VIEW_TEAMS)

    service = TeamService(session)
    teams = await service.list_teams(org_id)
    results = []
    for t in teams:
        results.append(TeamResponse(
            id=t.id,
            organization_id=t.organization_id,
            name=t.name,
            slug=t.slug,
            description=t.description,
            members_count=len(t.members),
            projects_count=len(t.project_access),
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))
    return results


@router.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> TeamResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_VIEW_TEAMS)

    service = TeamService(session)
    team = await service.get_team(org_id, team_id)
    return TeamResponse(
        id=team.id,
        organization_id=team.organization_id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        members_count=len(team.members),
        projects_count=len(team.project_access),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.patch("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> TeamResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_TEAMS)

    service = TeamService(session)
    team = await service.update_team(org_id, team_id, user.id, payload.model_dump(exclude_unset=True))
    return TeamResponse(
        id=team.id,
        organization_id=team.organization_id,
        name=team.name,
        slug=team.slug,
        description=team.description,
        members_count=len(team.members),
        projects_count=len(team.project_access),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_TEAMS)

    service = TeamService(session)
    await service.delete_team(org_id, team_id, user.id)


# ---------------------------------------------------------------------------
# Team Members
# ---------------------------------------------------------------------------
@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: UUID,
    payload: TeamMemberCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_TEAMS)

    service = TeamService(session)
    member = await service.add_member(org_id, team_id, user.id, payload.user_id, payload.role)
    target_user = await session.get(User, member.user_id)
    return TeamMemberResponse(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role=member.role,
        user_email=target_user.email if target_user else None,
        user_name=target_user.name if target_user else None,
        created_at=member.created_at,
    )


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[TeamMemberResponse]:
    service = TeamService(session)
    members = await service.list_members(org_id, team_id)
    return [TeamMemberResponse(**m) for m in members]


@router.delete("/teams/{team_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: UUID,
    target_user_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_TEAMS)

    service = TeamService(session)
    await service.remove_member(org_id, team_id, user.id, target_user_id)


# ---------------------------------------------------------------------------
# Team Project Access
# ---------------------------------------------------------------------------
@router.post("/teams/{team_id}/project-access", response_model=TeamProjectAccessResponse, status_code=status.HTTP_201_CREATED)
async def assign_team_project_access(
    team_id: UUID,
    payload: TeamProjectAccessCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> TeamProjectAccessResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_PROJECTS)

    service = TeamService(session)
    access = await service.assign_team_project_access(org_id, team_id, user.id, payload.project_id, payload.permission_role)
    return TeamProjectAccessResponse(
        id=access.id,
        team_id=access.team_id,
        project_id=access.project_id,
        permission_role=access.permission_role,
        created_at=access.created_at,
    )


@router.get("/teams/{team_id}/project-access", response_model=list[TeamProjectAccessResponse])
async def list_team_project_access(
    team_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[TeamProjectAccessResponse]:
    service = TeamService(session)
    items = await service.list_team_project_access(org_id, team_id)
    return [TeamProjectAccessResponse(**i) for i in items]


@router.delete("/teams/{team_id}/project-access/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_project_access(
    team_id: UUID,
    project_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_PROJECTS)

    service = TeamService(session)
    await service.remove_team_project_access(org_id, team_id, user.id, project_id)


# ---------------------------------------------------------------------------
# Direct Access & Permission Resolution
# ---------------------------------------------------------------------------
@router.post("/access/projects/{project_id}/users", response_model=UserProjectAccessResponse, status_code=status.HTTP_201_CREATED)
async def assign_direct_user_project_access(
    project_id: UUID,
    payload: UserProjectAccessCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> UserProjectAccessResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_PROJECTS)

    service = TeamService(session)
    access = await service.assign_user_project_access(org_id, project_id, user.id, payload.user_id, payload.permission_role)
    return UserProjectAccessResponse.model_validate(access)


@router.get("/access/resolve", response_model=AccessResolutionResponse)
async def resolve_access(
    project_id: UUID,
    target_user_id: UUID | None = None,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> AccessResolutionResponse:
    uid = target_user_id or user.id
    service = TeamService(session)
    res = await service.resolve_access(org_id, uid, project_id)
    return AccessResolutionResponse(**res)
