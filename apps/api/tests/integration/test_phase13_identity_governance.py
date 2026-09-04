"""Integration tests for Phase 13 Enterprise APIs."""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_identity_provider_crud_and_status_api(auth_client: AsyncClient):
    # 1. Create IdP
    create_payload = {
        "name": f"Okta-{uuid.uuid4().hex[:6]}",
        "provider_type": "OIDC",
        "client_id": "client_abc",
        "client_secret": "my-secret-key-12345",
        "issuer_url": "https://okta.example.com",
        "default_role": "ENGINEER",
        "enforce_sso": False,
    }
    res = await auth_client.post("/api/v1/identity-providers", json=create_payload)
    assert res.status_code == 201
    data = res.json()
    idp_id = data["id"]
    assert data["name"] == create_payload["name"]
    assert data["status"] == "DRAFT"
    # Secret must be masked!
    assert data["masked_client_secret"] is not None
    assert "2345" in data["masked_client_secret"]
    assert "my-secret-key" not in data["masked_client_secret"]

    # 2. List IdPs
    list_res = await auth_client.get("/api/v1/identity-providers")
    assert list_res.status_code == 200
    assert any(i["id"] == idp_id for i in list_res.json())

    # 3. Enable IdP
    enable_res = await auth_client.patch(f"/api/v1/identity-providers/{idp_id}/status?status_val=ACTIVE")
    assert enable_res.status_code == 200
    assert enable_res.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_domain_registration_and_verification_api(auth_client: AsyncClient):
    domain_name = f"enterprise-{uuid.uuid4().hex[:6]}.com"
    # 1. Register domain
    reg_res = await auth_client.post("/api/v1/domains", json={"domain": domain_name})
    assert reg_res.status_code == 201
    domain_data = reg_res.json()
    assert domain_data["domain"] == domain_name
    assert domain_data["status"] == "PENDING"
    domain_id = domain_data["id"]

    # 2. Verify domain
    ver_res = await auth_client.post(f"/api/v1/domains/{domain_id}/verify")
    assert ver_res.status_code == 200
    assert ver_res.json()["status"] == "VERIFIED"

    # 3. List domains
    list_res = await auth_client.get("/api/v1/domains")
    assert list_res.status_code == 200
    assert any(d["id"] == domain_id for d in list_res.json())


@pytest.mark.asyncio
async def test_sso_initiate_and_mock_callback_jit_provisioning(client: AsyncClient, auth_client: AsyncClient):
    domain = f"corp-{uuid.uuid4().hex[:6]}.com"
    # Register & verify domain
    dom_res = await auth_client.post("/api/v1/domains", json={"domain": domain})
    domain_id = dom_res.json()["id"]
    await auth_client.post(f"/api/v1/domains/{domain_id}/verify")

    # Create & activate mock IdP
    idp_res = await auth_client.post("/api/v1/identity-providers", json={
        "name": f"MockIdP-{uuid.uuid4().hex[:6]}",
        "provider_type": "MOCK",
        "default_role": "ENGINEER",
        "allowed_domains": [domain],
        "jit_provisioning_policy": "ALLOW_APPROVED_DOMAINS_ONLY",
    })
    idp_id = idp_res.json()["id"]
    await auth_client.patch(f"/api/v1/identity-providers/{idp_id}/status?status_val=ACTIVE")

    # Initiate SSO (public unauthenticated client)
    init_res = await client.post("/api/v1/identity-providers/sso/initiate", json={"domain": domain})
    assert init_res.status_code == 200
    assert init_res.json()["idp_id"] == idp_id

    # Complete SSO callback with new corporate user
    sso_email = f"alice@{domain}"
    cb_res = await client.post(f"/api/v1/identity-providers/{idp_id}/sso/callback", json={
        "mock_email": sso_email,
        "mock_name": "Alice Enterprise",
    })
    assert cb_res.status_code == 200
    tokens = cb_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["user"]["email"] == sso_email


@pytest.mark.asyncio
async def test_team_and_member_management_api(auth_client: AsyncClient):
    team_name = f"RedTeam-{uuid.uuid4().hex[:6]}"
    # 1. Create team
    create_res = await auth_client.post("/api/v1/teams", json={"name": team_name, "description": "Red Team"})
    assert create_res.status_code == 201
    team_data = create_res.json()
    team_id = team_data["id"]

    # 2. List teams
    list_res = await auth_client.get("/api/v1/teams")
    assert list_res.status_code == 200
    assert any(t["id"] == team_id for t in list_res.json())

    # 3. List members
    mem_res = await auth_client.get(f"/api/v1/teams/{team_id}/members")
    assert mem_res.status_code == 200
    assert len(mem_res.json()) >= 1  # creator is LEAD


@pytest.mark.asyncio
async def test_approval_workflow_lifecycle_api(auth_client: AsyncClient, client: AsyncClient):
    # 1. Create approval request
    req_res = await auth_client.post("/api/v1/approvals", json={
        "target_type": "RELEASE_DECISION",
        "target_id": str(uuid.uuid4()),
        "title": "Staging Release Approval",
        "description": "Approve deploy to staging",
    })
    assert req_res.status_code == 201
    req_data = req_res.json()
    req_id = req_data["id"]
    assert req_data["status"] == "PENDING"

    # 2. Attempt self-approval -> must be 403 Forbidden!
    self_approve_res = await auth_client.post(f"/api/v1/approvals/{req_id}/action", json={
        "outcome": "APPROVED",
        "comments": "Self approving my own request",
    })
    assert self_approve_res.status_code == 403
    assert "Self-approval is prohibited" in self_approve_res.text


@pytest.mark.asyncio
async def test_access_review_campaign_lifecycle_api(auth_client: AsyncClient):
    # 1. Create review campaign
    create_res = await auth_client.post("/api/v1/access-reviews", json={"title": "Q3 Access Review"})
    assert create_res.status_code == 201
    rev_data = create_res.json()
    rev_id = rev_data["id"]
    assert rev_data["status"] == "OPEN"
    assert len(rev_data["items"]) > 0

    # 2. Decide first item as KEEP
    first_item = rev_data["items"][0]
    dec_res = await auth_client.post(f"/api/v1/access-reviews/{rev_id}/items/{first_item['id']}/decision", json={
        "decision": "KEEP",
        "notes": "Verified active engineer",
    })
    assert dec_res.status_code == 200
    assert dec_res.json()["decision"] == "KEEP"

    # 3. Complete review
    comp_res = await auth_client.post(f"/api/v1/access-reviews/{rev_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "COMPLETED"
