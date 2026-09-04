"""Unit tests for Phase 13 Enterprise Identity, Collaboration & Governance."""

from __future__ import annotations

import uuid
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

from app.core.errors import ConflictError, ForbiddenError, ValidationFailure
from app.core.permissions import Role, resolve_user_project_access
from app.core.secret_manager import SecretManager, mask_secret
from app.models.identity import IdentityProvider, OrganizationDomain
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.team import Team, TeamMember, TeamProjectAccess, UserProjectAccess
from app.models.governance import ApprovalRequest, GovernancePolicy
from app.services.identity_service import IdentityService
from app.services.team_service import TeamService
from app.services.governance_service import GovernanceService


@pytest.mark.asyncio
async def test_idp_secret_encryption_and_masking(db_session):
    mgr = SecretManager()
    plain = "super-secret-oauth-client-key-1234"
    enc = mgr.encrypt(plain)
    assert enc != plain
    dec = mgr.decrypt(enc)
    assert dec == plain

    masked = mask_secret(dec)
    assert "1234" in masked
    assert "super-secret" not in masked
    assert "****" in masked


@pytest.mark.asyncio
async def test_idp_default_role_cannot_be_owner(db_session):
    service = IdentityService(db_session)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Create dummy org
    org = Organization(id=org_id, name="Security Org", slug=f"sec-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()

    with pytest.raises(ValidationFailure, match="cannot be OWNER"):
        await service.create_idp(
            org_id=org_id,
            user_id=user_id,
            data={
                "name": "Malicious IdP",
                "provider_type": "OIDC",
                "default_role": "OWNER",  # Violation
            },
        )


@pytest.mark.asyncio
async def test_domain_registration_and_token_generation(db_session):
    service = IdentityService(db_session)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    org = Organization(id=org_id, name="Acme Corp", slug=f"acme-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()

    domain = await service.register_domain(org_id, user_id, "acme.com", method="DNS_TXT")
    assert domain.domain == "acme.com"
    assert domain.status == "PENDING"
    assert domain.verification_token.startswith("airex-verification-")

    # Verify domain
    verified = await service.verify_domain(org_id, domain.id, user_id)
    assert verified.status == "VERIFIED"
    assert verified.verified_at is not None


@pytest.mark.asyncio
async def test_team_slug_generation(db_session):
    service = TeamService(db_session)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    org = Organization(id=org_id, name="Team Org", slug=f"team-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.commit()

    team = await service.create_team(org_id, user_id, "Red Team Alpha", "Security evaluation team")
    assert team.name == "Red Team Alpha"
    assert team.slug == "red-team-alpha"


@pytest.mark.asyncio
async def test_project_access_resolution_precedence(db_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()

    org = Organization(id=org_id, name="Access Org", slug=f"access-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    # 1. No access
    role, access_type = await resolve_user_project_access(db_session, user_id, project_id, org_id)
    assert role is None
    assert access_type == "NO_ACCESS"

    # 2. Organization access (as ENGINEER)
    org_mem = OrganizationMember(organization_id=org_id, user_id=user_id, role="ENGINEER", created_at=datetime.now(UTC))
    db_session.add(org_mem)
    await db_session.flush()

    role, access_type = await resolve_user_project_access(db_session, user_id, project_id, org_id)
    assert role == Role.ENGINEER
    assert access_type == "ORGANIZATION_ACCESS"

    # 3. Team access overrides with higher/explicit role
    team = Team(organization_id=org_id, name="Dev Team", slug="dev-team")
    db_session.add(team)
    await db_session.flush()

    team_mem = TeamMember(team_id=team.id, user_id=user_id, role="MEMBER", created_at=datetime.now(UTC))
    db_session.add(team_mem)
    team_acc = TeamProjectAccess(team_id=team.id, project_id=project_id, permission_role="ADMIN", created_at=datetime.now(UTC))
    db_session.add(team_acc)
    await db_session.flush()

    role, access_type = await resolve_user_project_access(db_session, user_id, project_id, org_id)
    assert role == Role.ADMIN
    assert access_type == "TEAM_ACCESS"

    # 4. Direct user access takes top precedence
    direct_acc = UserProjectAccess(user_id=user_id, project_id=project_id, permission_role="VIEWER", created_at=datetime.now(UTC))
    db_session.add(direct_acc)
    await db_session.flush()

    role, access_type = await resolve_user_project_access(db_session, user_id, project_id, org_id)
    assert role == Role.VIEWER
    assert access_type == "DIRECT_ACCESS"


@pytest.mark.asyncio
async def test_approval_self_approval_prohibition_unit(db_session):
    gov_service = GovernanceService(db_session)
    org_id = uuid.uuid4()
    requester_id = uuid.uuid4()

    req = await gov_service.create_approval_request(
        org_id=org_id,
        requester_id=requester_id,
        data={
            "target_type": "RELEASE_DECISION",
            "target_id": str(uuid.uuid4()),
            "title": "Release Approval",
        },
    )
    assert req.status == "PENDING"

    # Self approval must raise ForbiddenError
    with pytest.raises(ForbiddenError, match="Self-approval is prohibited"):
        await gov_service.act_on_approval(
            org_id=org_id,
            request_id=req.id,
            approver_id=requester_id,  # SAME as requester!
            outcome="APPROVED",
        )


@pytest.mark.asyncio
async def test_governance_policy_version_auto_increment(db_session):
    gov_service = GovernanceService(db_session)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    p1 = await gov_service.create_policy(org_id, user_id, {"name": "Safety Baseline", "description": "v1"})
    assert p1.version == 1

    p2 = await gov_service.create_policy(org_id, user_id, {"name": "Safety Baseline", "description": "v2"})
    assert p2.version == 2
