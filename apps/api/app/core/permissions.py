"""Role-based access control (PRD §7, spec §13, AT-013/014; Phase 13 Enterprise RBAC).

Roles: OWNER, ADMIN, ENGINEER, VIEWER.
Capability-based checks are used by services and API dependencies.
Deterministic resolution: DIRECT_ACCESS > TEAM_ACCESS > ORGANIZATION_ACCESS.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"
    VIEWER = "VIEWER"


# Role priority rank for deterministic conflict resolution
ROLE_HIERARCHY = {
    Role.OWNER: 4,
    Role.ADMIN: 3,
    Role.ENGINEER: 2,
    Role.VIEWER: 1,
}


# Capability strings used across the API.
CAP_MANAGE_ORGANIZATION = "manage_organization"
CAP_MANAGE_USERS = "manage_users"
CAP_MANAGE_PROJECTS = "manage_projects"
CAP_MANAGE_MODELS = "manage_models"
CAP_MANAGE_DATASETS = "manage_datasets"
CAP_RUN_EVALUATIONS = "run_evaluations"
CAP_CREATE_EXPERIMENTS = "create_experiments"
CAP_VIEW_ALL = "view_all"
CAP_VIEW_AUDIT = "view_audit"
# Phase 1 capabilities.
CAP_MANAGE_MEMBERS = "manage_members"
CAP_VIEW_MEMBERS = "view_members"
CAP_MANAGE_PROVIDERS = "manage_providers"
CAP_MANAGE_ENVIRONMENTS = "manage_environments"
CAP_INVOKE_MODELS = "invoke_models"
# Phase 4.
CAP_MANAGE_RUBRICS = "manage_rubrics"
# Phase 5.
CAP_GENERATE_TESTS = "generate_tests"
# Phase 13 Enterprise Capabilities.
CAP_MANAGE_TEAMS = "manage_teams"
CAP_VIEW_TEAMS = "view_teams"
CAP_MANAGE_IDENTITY = "manage_identity"
CAP_MANAGE_DOMAINS = "manage_domains"
CAP_MANAGE_GOVERNANCE = "manage_governance"
CAP_ACT_APPROVALS = "act_approvals"
CAP_MANAGE_REVIEWS = "manage_reviews"
CAP_MANAGE_TOKENS = "manage_tokens"
# Phase 14 Compliance & Data Governance Capabilities.
CAP_MANAGE_COMPLIANCE = "manage_compliance"
CAP_RUN_COMPLIANCE_ASSESSMENTS = "run_compliance_assessments"
CAP_MANAGE_RETENTION = "manage_retention"
CAP_MANAGE_LEGAL_HOLDS = "manage_legal_holds"
CAP_EXPORT_COMPLIANCE_REPORTS = "export_compliance_reports"

# Role -> capabilities (least-privilege defaults; see PERMISSION_MATRIX).
_ROLE_CAPABILITIES: dict[Role, set[str]] = {
    Role.OWNER: {
        CAP_MANAGE_ORGANIZATION,
        CAP_MANAGE_USERS,
        CAP_MANAGE_PROJECTS,
        CAP_MANAGE_MODELS,
        CAP_MANAGE_DATASETS,
        CAP_RUN_EVALUATIONS,
        CAP_CREATE_EXPERIMENTS,
        CAP_VIEW_ALL,
        CAP_VIEW_AUDIT,
        CAP_MANAGE_MEMBERS,
        CAP_VIEW_MEMBERS,
        CAP_MANAGE_PROVIDERS,
        CAP_MANAGE_ENVIRONMENTS,
        CAP_INVOKE_MODELS,
        CAP_MANAGE_RUBRICS,
        CAP_GENERATE_TESTS,
        CAP_MANAGE_TEAMS,
        CAP_VIEW_TEAMS,
        CAP_MANAGE_IDENTITY,
        CAP_MANAGE_DOMAINS,
        CAP_MANAGE_GOVERNANCE,
        CAP_ACT_APPROVALS,
        CAP_MANAGE_REVIEWS,
        CAP_MANAGE_TOKENS,
        CAP_MANAGE_COMPLIANCE,
        CAP_RUN_COMPLIANCE_ASSESSMENTS,
        CAP_MANAGE_RETENTION,
        CAP_MANAGE_LEGAL_HOLDS,
        CAP_EXPORT_COMPLIANCE_REPORTS,
    },
    Role.ADMIN: {
        CAP_MANAGE_ORGANIZATION,
        CAP_MANAGE_USERS,
        CAP_MANAGE_PROJECTS,
        CAP_MANAGE_MODELS,
        CAP_MANAGE_DATASETS,
        CAP_RUN_EVALUATIONS,
        CAP_CREATE_EXPERIMENTS,
        CAP_VIEW_ALL,
        CAP_VIEW_AUDIT,
        CAP_MANAGE_MEMBERS,
        CAP_VIEW_MEMBERS,
        CAP_MANAGE_PROVIDERS,
        CAP_MANAGE_ENVIRONMENTS,
        CAP_INVOKE_MODELS,
        CAP_MANAGE_RUBRICS,
        CAP_GENERATE_TESTS,
        CAP_MANAGE_TEAMS,
        CAP_VIEW_TEAMS,
        CAP_MANAGE_IDENTITY,
        CAP_MANAGE_DOMAINS,
        CAP_MANAGE_GOVERNANCE,
        CAP_ACT_APPROVALS,
        CAP_MANAGE_REVIEWS,
        CAP_MANAGE_TOKENS,
        CAP_MANAGE_COMPLIANCE,
        CAP_RUN_COMPLIANCE_ASSESSMENTS,
        CAP_MANAGE_RETENTION,
        CAP_MANAGE_LEGAL_HOLDS,
        CAP_EXPORT_COMPLIANCE_REPORTS,
    },
    Role.ENGINEER: {
        CAP_MANAGE_DATASETS,
        CAP_RUN_EVALUATIONS,
        CAP_CREATE_EXPERIMENTS,
        CAP_VIEW_ALL,
        CAP_VIEW_MEMBERS,
        CAP_INVOKE_MODELS,
        CAP_MANAGE_RUBRICS,
        CAP_GENERATE_TESTS,
        CAP_VIEW_TEAMS,
        CAP_VIEW_AUDIT,
        CAP_RUN_COMPLIANCE_ASSESSMENTS,
        CAP_EXPORT_COMPLIANCE_REPORTS,
    },
    Role.VIEWER: {
        CAP_VIEW_ALL,
        CAP_VIEW_MEMBERS,
        CAP_VIEW_TEAMS,
        CAP_VIEW_AUDIT,
        CAP_EXPORT_COMPLIANCE_REPORTS,
    },
}


def has_capability(role: Role | str, capability: str) -> bool:
    try:
        r = Role(role)
    except ValueError:
        return False
    return capability in _ROLE_CAPABILITIES.get(r, set())


def require_capability(role: Role | str, capability: str) -> None:
    """Raise ForbiddenError when the role lacks the capability (AT-013)."""
    if not has_capability(role, capability):
        raise ForbiddenError(
            "You do not have permission to perform this action.",
            details={"required_capability": capability},
        )


async def resolve_user_project_access(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    org_id: UUID,
) -> tuple[Role | None, str]:
    """Deterministically resolve user project permissions with explicit precedence:
    
    1. DIRECT_ACCESS: Explicit direct assignment on project (UserProjectAccess)
    2. TEAM_ACCESS: Access granted through team memberships (TeamProjectAccess)
    3. ORGANIZATION_ACCESS: Inherited organization role (OrganizationMember OWNER / ADMIN, or unrestricted fallback)
    4. NO_ACCESS: Returns (None, "NO_ACCESS")
    """
    from app.models.team import TeamMember, TeamProjectAccess, UserProjectAccess
    from app.models.organization import OrganizationMember
    from app.models.project import Project

    # Cross-tenant boundary check
    project = await session.get(Project, project_id)
    if project is not None and project.organization_id != org_id:
        return None, "NO_ACCESS"

    # Verify organization membership
    stmt_org = select(OrganizationMember).where(
        and_(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    res_org = await session.execute(stmt_org)
    org_member = res_org.scalars().first()
    if not org_member:
        return None, "NO_ACCESS"

    try:
        org_role = Role(org_member.role)
    except ValueError:
        return None, "NO_ACCESS"

    # 1. Direct User Assignment
    stmt_direct = select(UserProjectAccess).where(
        and_(
            UserProjectAccess.user_id == user_id,
            UserProjectAccess.project_id == project_id,
        )
    )
    res_direct = await session.execute(stmt_direct)
    direct = res_direct.scalars().first()
    if direct:
        try:
            return Role(direct.permission_role), "DIRECT_ACCESS"
        except ValueError:
            pass

    # 2. Team Membership Assignment
    stmt_team = (
        select(TeamProjectAccess.permission_role)
        .join(TeamMember, TeamMember.team_id == TeamProjectAccess.team_id)
        .where(
            and_(
                TeamMember.user_id == user_id,
                TeamProjectAccess.project_id == project_id,
            )
        )
    )
    res_team = await session.execute(stmt_team)
    team_roles = res_team.scalars().all()
    if team_roles:
        best_role = Role.VIEWER
        best_rank = 1
        for r_str in team_roles:
            try:
                r = Role(r_str)
                rank = ROLE_HIERARCHY.get(r, 0)
                if rank > best_rank:
                    best_rank = rank
                    best_role = r
            except ValueError:
                pass
        return best_role, "TEAM_ACCESS"

    # 3. Organization Membership Fallback
    if org_role in (Role.OWNER, Role.ADMIN):
        return org_role, "ORGANIZATION_ACCESS"

    # For non-admin members, check if project has explicit access lists defined
    stmt_has_direct = select(UserProjectAccess.id).where(UserProjectAccess.project_id == project_id).limit(1)
    has_direct_restrictions = (await session.execute(stmt_has_direct)).first() is not None
    stmt_has_team = select(TeamProjectAccess.id).where(TeamProjectAccess.project_id == project_id).limit(1)
    has_team_restrictions = (await session.execute(stmt_has_team)).first() is not None

    if has_direct_restrictions or has_team_restrictions:
        # Project is restricted to specific users/teams; user has neither
        return None, "NO_ACCESS"

    # Unrestricted project: organization role applies
    return org_role, "ORGANIZATION_ACCESS"
