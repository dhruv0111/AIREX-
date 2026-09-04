"""Phase 10 Security Tests: RBAC, Tenant Isolation, Input Validation, and Sensitive Data Protection."""

from __future__ import annotations

import pytest
from uuid import uuid4

from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)


async def _setup_users_and_project(client):
    # Owner user
    owner_email = f"owner_{uuid4().hex[:8]}@example.com"
    await register(client, owner_email)
    owner_headers = await headers_for(client, owner_email)
    owner_org = await org_id(client, owner_headers)
    project_id = await create_project(client, owner_headers, owner_org, name="Security Proj")

    # Viewer user in the same org
    viewer_email = f"viewer_{uuid4().hex[:8]}@example.com"
    await register(client, viewer_email)
    viewer_headers = await headers_for(client, viewer_email)

    # Add viewer to organization with VIEWER role
    add_resp = await client.post(
        f"/api/v1/organizations/{owner_org}/members",
        json={"email": viewer_email, "role": "VIEWER"},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert add_resp.status_code == 201, add_resp.text

    # Cross-tenant attacker in a completely different organization
    attacker_email = f"attacker_{uuid4().hex[:8]}@example.com"
    await register(client, attacker_email)
    attacker_headers = await headers_for(client, attacker_email)
    attacker_org = await org_id(client, attacker_headers)

    return (
        owner_headers,
        owner_org,
        viewer_headers,
        attacker_headers,
        attacker_org,
        project_id,
    )


@pytest.mark.asyncio
async def test_rbac_viewer_cannot_create_or_evaluate(client):
    (
        owner_headers,
        owner_org,
        viewer_headers,
        _,
        _,
        project_id,
    ) = await _setup_users_and_project(client)

    # 1. Viewer attempts to create policy -> 403 Forbidden
    resp = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": "Viewer Policy", "min_reliability_score": 80.0},
        headers={**viewer_headers, "X-Organization-Id": owner_org},
    )
    assert resp.status_code == 403

    # 2. Owner creates a valid policy
    pol_resp = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": "Owner Policy", "min_reliability_score": 80.0},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert pol_resp.status_code == 201
    policy_id = pol_resp.json()["data"]["id"]

    # 3. Viewer can READ the policy -> 200 OK
    get_resp = await client.get(
        f"/api/v1/projects/{project_id}/release-policies/{policy_id}",
        headers={**viewer_headers, "X-Organization-Id": owner_org},
    )
    assert get_resp.status_code == 200

    # 4. Viewer attempts to update policy -> 403 Forbidden
    put_resp = await client.put(
        f"/api/v1/projects/{project_id}/release-policies/{policy_id}",
        json={"min_reliability_score": 90.0},
        headers={**viewer_headers, "X-Organization-Id": owner_org},
    )
    assert put_resp.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation_cross_org_returns_404(client):
    (
        owner_headers,
        owner_org,
        _,
        attacker_headers,
        attacker_org,
        project_id,
    ) = await _setup_users_and_project(client)

    # Owner creates policy
    pol_resp = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": "Confidential Policy", "min_reliability_score": 85.0},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert pol_resp.status_code == 201
    policy_id = pol_resp.json()["data"]["id"]

    # Attacker attempts to list or read policies of the victim's project -> 404 Not Found
    resp_list = await client.get(
        f"/api/v1/projects/{project_id}/release-policies",
        headers={**attacker_headers, "X-Organization-Id": attacker_org},
    )
    assert resp_list.status_code == 404

    resp_get = await client.get(
        f"/api/v1/projects/{project_id}/release-policies/{policy_id}",
        headers={**attacker_headers, "X-Organization-Id": attacker_org},
    )
    assert resp_get.status_code == 404

    # Attacker attempts to access project intelligence overview -> 404 Not Found
    resp_intel = await client.get(
        f"/api/v1/projects/{project_id}/intelligence/overview",
        headers={**attacker_headers, "X-Organization-Id": attacker_org},
    )
    assert resp_intel.status_code == 404


@pytest.mark.asyncio
async def test_input_validation_and_injection_defense(client):
    (
        owner_headers,
        owner_org,
        _,
        _,
        _,
        project_id,
    ) = await _setup_users_and_project(client)

    # Negative latency -> 400 or 422
    resp1 = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": "Invalid Policy", "max_latency_ms": -100.0},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert resp1.status_code in (400, 422)

    # Negative cost -> 400 or 422
    resp2 = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": "Invalid Cost Policy", "max_cost": -5.0},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert resp2.status_code in (400, 422)

    # Reliability score > 100 -> 400 or 422
    resp3 = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": "Invalid Score Policy", "min_reliability_score": 150.0},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert resp3.status_code in (400, 422)

    # SQL injection attempt in name safely sanitized
    sql_name = "'; DROP TABLE release_policies; --"
    resp4 = await client.post(
        f"/api/v1/projects/{project_id}/release-policies",
        json={"name": sql_name, "min_reliability_score": 80.0},
        headers={**owner_headers, "X-Organization-Id": owner_org},
    )
    assert resp4.status_code == 201
    assert resp4.json()["data"]["name"] == sql_name
