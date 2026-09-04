"""Phase 11 Security Tests: RBAC, Tenant Isolation, Input Validation, and Sensitive Data Protection."""

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
    project_id = await create_project(client, owner_headers, owner_org, name="Agent Security Proj")

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
async def test_rbac_viewer_cannot_mutate_agents_or_tools(client):
    """Viewers must be forbidden (HTTP 403) from creating agents, tools, or triggering runs."""
    (
        owner_headers,
        owner_org,
        viewer_headers,
        _,
        _,
        project_id,
    ) = await _setup_users_and_project(client)

    v_headers = {**viewer_headers, "X-Organization-Id": owner_org}
    o_headers = {**owner_headers, "X-Organization-Id": owner_org}

    # 1. Viewer cannot create a tool
    tool_resp = await client.post(
        f"/api/v1/projects/{project_id}/tools",
        json={"name": "test_tool", "input_schema": {"type": "object"}},
        headers=v_headers,
    )
    assert tool_resp.status_code == 403, tool_resp.text

    # 2. Viewer cannot create an agent
    agent_resp = await client.post(
        f"/api/v1/projects/{project_id}/agents",
        json={"name": "test_agent", "agent_type": "TOOL_AGENT"},
        headers=v_headers,
    )
    assert agent_resp.status_code == 403, agent_resp.text

    # Owner creates agent
    o_agent = await client.post(
        f"/api/v1/projects/{project_id}/agents",
        json={"name": "owner_agent", "agent_type": "TOOL_AGENT"},
        headers=o_headers,
    )
    assert o_agent.status_code == 201
    agent_id = o_agent.json()["data"]["id"]

    # 3. Viewer cannot trigger a run
    run_resp = await client.post(
        f"/api/v1/projects/{project_id}/agents/{agent_id}/runs",
        json={"task": {"task_id": "t1", "instruction": "do something"}},
        headers=v_headers,
    )
    assert run_resp.status_code == 403, run_resp.text


@pytest.mark.asyncio
async def test_tenant_isolation_cross_org_access_forbidden(client):
    """Cross-tenant requests must return HTTP 404 (NotFoundError), never leaking existence."""
    (
        owner_headers,
        owner_org,
        _,
        attacker_headers,
        attacker_org,
        project_id,
    ) = await _setup_users_and_project(client)

    o_headers = {**owner_headers, "X-Organization-Id": owner_org}
    att_headers = {**attacker_headers, "X-Organization-Id": attacker_org}

    # Owner creates agent
    o_agent = await client.post(
        f"/api/v1/projects/{project_id}/agents",
        json={"name": "private_agent", "agent_type": "TOOL_AGENT"},
        headers=o_headers,
    )
    assert o_agent.status_code == 201
    agent_id = o_agent.json()["data"]["id"]

    # Attacker tries to read agent in another tenant's project
    att_resp = await client.get(
        f"/api/v1/projects/{project_id}/agents/{agent_id}",
        headers=att_headers,
    )
    assert att_resp.status_code == 404, att_resp.text

    # Attacker tries to list agents in another tenant's project
    att_list = await client.get(
        f"/api/v1/projects/{project_id}/agents",
        headers=att_headers,
    )
    assert att_list.status_code == 404, att_list.text
