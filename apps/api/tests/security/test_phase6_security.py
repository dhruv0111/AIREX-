"""Phase 6 security tests for RBAC capabilities and multi-tenant containment."""

from __future__ import annotations

import pytest
from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)

EMAIL_OWNER = "sec-owner@example.com"
EMAIL_ENGINEER = "sec-engineer@example.com"
EMAIL_VIEWER = "sec-viewer@example.com"
EMAIL_OTHER = "sec-other@example.com"


async def _setup_users(client):
    # Register all users
    await register(client, EMAIL_OWNER)
    await register(client, EMAIL_ENGINEER)
    await register(client, EMAIL_VIEWER)
    await register(client, EMAIL_OTHER)

    owner_headers = await headers_for(client, EMAIL_OWNER)
    org = await org_id(client, owner_headers)
    project = await create_project(client, owner_headers, org, name="Security Proj")

    # Add engineer to org
    add_eng = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": EMAIL_ENGINEER, "role": "ENGINEER"},
        headers={**owner_headers, "X-Organization-Id": org},
    )
    assert add_eng.status_code == 201

    # Add viewer to org
    add_view = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": EMAIL_VIEWER, "role": "VIEWER"},
        headers={**owner_headers, "X-Organization-Id": org},
    )
    assert add_view.status_code == 201

    # Return tokens and context
    eng_headers = await headers_for(client, EMAIL_ENGINEER)
    view_headers = await headers_for(client, EMAIL_VIEWER)
    other_headers = await headers_for(client, EMAIL_OTHER)

    return org, project, owner_headers, eng_headers, view_headers, other_headers


@pytest.mark.asyncio
async def test_rbac_experiment_permissions(client):
    org, project, owner_headers, eng_headers, view_headers, other_headers = await _setup_users(client)

    # 1. Viewers CANNOT create experiments
    resp_viewer = await client.post(
        f"/api/v1/projects/{project}/experiments",
        json={
            "project_id": project,
            "name": "Viewer Try",
            "experiment_type": "MODEL_COMPARISON",
            "baseline": {},
            "candidate": {},
        },
        headers={**view_headers, "X-Organization-Id": org},
    )
    assert resp_viewer.status_code in (403, 401)

    # 2. Engineers CAN create experiments
    resp_eng = await client.post(
        f"/api/v1/projects/{project}/experiments",
        json={
            "project_id": project,
            "name": "Engineer Success",
            "experiment_type": "MODEL_COMPARISON",
            "baseline": {},
            "candidate": {},
        },
        headers={**eng_headers, "X-Organization-Id": org},
    )
    assert resp_eng.status_code == 201
    exp_id = resp_eng.json()["data"]["id"]

    # 3. Viewers CAN read experiments
    resp_read_viewer = await client.get(
        f"/api/v1/experiments/{exp_id}",
        headers={**view_headers, "X-Organization-Id": org},
    )
    assert resp_read_viewer.status_code == 200

    # 4. Viewers CANNOT trigger runs
    resp_run_viewer = await client.post(
        f"/api/v1/experiments/{exp_id}/run",
        headers={**view_headers, "X-Organization-Id": org},
    )
    assert resp_run_viewer.status_code in (403, 401)


@pytest.mark.asyncio
async def test_multi_tenant_containment(client):
    org, project, owner_headers, eng_headers, view_headers, other_headers = await _setup_users(client)

    # Owner creates an experiment
    resp_exp = await client.post(
        f"/api/v1/projects/{project}/experiments",
        json={
            "project_id": project,
            "name": "Tenant Secret Exp",
            "experiment_type": "MODEL_COMPARISON",
            "baseline": {},
            "candidate": {},
        },
        headers={**owner_headers, "X-Organization-Id": org},
    )
    assert resp_exp.status_code == 201
    exp_id = resp_exp.json()["data"]["id"]

    # Other user registered (external org) tries to access the experiment
    # They shouldn't have memberships or correct organization headers for this org
    resp_leak = await client.get(
        f"/api/v1/experiments/{exp_id}",
        headers={**other_headers, "X-Organization-Id": org},
    )
    assert resp_leak.status_code in (403, 404, 401)
