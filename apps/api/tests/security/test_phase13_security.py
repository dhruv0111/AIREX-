"""Security and negative tests for Phase 13 Enterprise Governance."""

from __future__ import annotations

from datetime import datetime, UTC
import uuid
import pytest
from httpx import AsyncClient

from app.models.organization import Organization, OrganizationMember
from app.models.identity import IdentityProvider, OrganizationDomain
from app.models.user import User


@pytest.mark.asyncio
async def test_domain_takeover_and_cross_org_collision_prevention(client: AsyncClient, auth_client: AsyncClient):
    # Org A registers domain
    domain = f"corp-{uuid.uuid4().hex[:6]}.com"
    reg_a = await auth_client.post("/api/v1/domains", json={"domain": domain})
    assert reg_a.status_code == 201

    # User B registers on different organization
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"name": "Bob Competitor", "email": f"bob-{uuid.uuid4().hex[:6]}@example.com", "password": "Password123!"},
    )
    tokens_b = reg_b.json()["data"]
    org_res_b = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {tokens_b['access_token']}"})
    org_b_id = org_res_b.json()["data"][0]["id"]

    headers_b = {
        "Authorization": f"Bearer {tokens_b['access_token']}",
        "X-Organization-Id": org_b_id,
    }

    # Org B attempts to register the exact same domain
    reg_dup = await client.post("/api/v1/domains", json={"domain": domain}, headers=headers_b)
    assert reg_dup.status_code == 409
    assert "already registered" in reg_dup.text


@pytest.mark.asyncio
async def test_jit_privilege_escalation_prevention(client: AsyncClient, auth_client: AsyncClient):
    domain = f"safe-{uuid.uuid4().hex[:6]}.com"
    dom_res = await auth_client.post("/api/v1/domains", json={"domain": domain})
    dom_id = dom_res.json()["id"]
    await auth_client.post(f"/api/v1/domains/{dom_id}/verify")

    # Attacker tries to create IdP configured with OWNER default role -> must be 422/400 ValidationFailure!
    bad_idp = await auth_client.post("/api/v1/identity-providers", json={
        "name": "Exploit IdP",
        "provider_type": "MOCK",
        "default_role": "OWNER",  # Disallowed!
        "allowed_domains": [domain],
    })
    assert bad_idp.status_code in (400, 422)
    assert "cannot be OWNER" in bad_idp.text


@pytest.mark.asyncio
async def test_jit_unapproved_domain_rejected(client: AsyncClient, auth_client: AsyncClient):
    domain = f"approved-{uuid.uuid4().hex[:6]}.com"
    dom_res = await auth_client.post("/api/v1/domains", json={"domain": domain})
    dom_id = dom_res.json()["id"]
    await auth_client.post(f"/api/v1/domains/{dom_id}/verify")

    idp_res = await auth_client.post("/api/v1/identity-providers", json={
        "name": "Strict IdP",
        "provider_type": "MOCK",
        "default_role": "VIEWER",
        "allowed_domains": [domain],
        "jit_provisioning_policy": "ALLOW_APPROVED_DOMAINS_ONLY",
    })
    idp_id = idp_res.json()["id"]
    await auth_client.patch(f"/api/v1/identity-providers/{idp_id}/status?status_val=ACTIVE")

    # Attempt callback with an unapproved domain (e.g. evil.com)
    evil_cb = await client.post(f"/api/v1/identity-providers/{idp_id}/sso/callback", json={
        "mock_email": "attacker@evil-domain.com",
        "mock_name": "Attacker",
    })
    assert evil_cb.status_code == 403
    assert "not approved for automatic JIT provisioning" in evil_cb.text


@pytest.mark.asyncio
async def test_self_approval_bypass_blocked(auth_client: AsyncClient):
    req_res = await auth_client.post("/api/v1/approvals", json={
        "target_type": "RELEASE_DECISION",
        "target_id": str(uuid.uuid4()),
        "title": "Critical Security Release",
    })
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]

    # Requester cannot approve their own request
    act_res = await auth_client.post(f"/api/v1/approvals/{req_id}/action", json={
        "outcome": "APPROVED",
        "comments": "Approving myself",
    })
    assert act_res.status_code == 403
    assert "Self-approval is prohibited" in act_res.text


@pytest.mark.asyncio
async def test_completed_approval_tampering_rejected(client: AsyncClient, auth_client: AsyncClient, db_session):
    # 1. User A creates approval request
    req_res = await auth_client.post("/api/v1/approvals", json={
        "target_type": "RELEASE_DECISION",
        "target_id": str(uuid.uuid4()),
        "title": "Dual Control Release",
    })
    req_id = req_res.json()["id"]
    org_id = req_res.json()["organization_id"]

    # 2. Register User B
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"name": "Approver B", "email": f"approver-{uuid.uuid4().hex[:6]}@example.com", "password": "Password123!"},
    )
    tokens_b = reg_b.json()["data"]
    me_b = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens_b['access_token']}"})
    user_b_id = me_b.json()["data"]["user"]["id"]

    # Add User B to User A's organization as ADMIN
    mem_b = OrganizationMember(
        organization_id=uuid.UUID(org_id),
        user_id=uuid.UUID(user_b_id),
        role="ADMIN",
        created_at=datetime.now(UTC),
    )
    db_session.add(mem_b)
    await db_session.commit()

    headers_b = {
        "Authorization": f"Bearer {tokens_b['access_token']}",
        "X-Organization-Id": org_id,
    }

    # User B approves the request
    app_res = await client.post(f"/api/v1/approvals/{req_id}/action", json={"outcome": "APPROVED"}, headers=headers_b)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"

    # 3. Attempting to tamper/re-decide an already decided approval must fail with 409 Conflict
    tamper_res = await client.post(f"/api/v1/approvals/{req_id}/action", json={"outcome": "REJECTED"}, headers=headers_b)
    assert tamper_res.status_code == 409
    assert "already APPROVED" in tamper_res.text


@pytest.mark.asyncio
async def test_secret_leakage_prevention_in_api(auth_client: AsyncClient):
    secret_val = "super-secret-production-token-998877"
    res = await auth_client.post("/api/v1/identity-providers", json={
        "name": f"SecretCheck-{uuid.uuid4().hex[:6]}",
        "client_secret": secret_val,
        "default_role": "VIEWER",
    })
    assert res.status_code == 201
    body_text = res.text
    # Secret must never be in body in plaintext
    assert secret_val not in body_text
    assert "8877" in body_text  # masked suffix
