"""Security and multi-tenant isolation boundary tests for Observability and Alerting (Phase 8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from datetime import datetime, UTC
from uuid import uuid4, UUID

from tests.integration._helpers import create_project, headers_for, org_id, register
from app.models.trace import Trace
from app.models.alert import AlertRule
from app.models.organization import OrganizationMember
from app.core.permissions import Role

EMAIL_A = "sec_obs_a@example.com"
EMAIL_B = "sec_obs_b@example.com"
EMAIL_VIEWER = "viewer_obs@example.com"


@pytest.mark.asyncio
async def test_cross_project_trace_access_isolation(client: AsyncClient, session_factory) -> None:
    # 1. Register User A and create Project A + Trace A
    await register(client, EMAIL_A)
    headers_a = await headers_for(client, EMAIL_A)
    org_a = await org_id(client, headers_a)
    project_a = await create_project(client, headers_a, org_a, name="Project A")

    async with session_factory() as db_session:
        trace_a_id = f"trace_sec_{uuid4()}"
        trace_a = Trace(
            id=uuid4(),
            project_id=UUID(project_a),
            organization_id=UUID(org_a),
            trace_id=trace_a_id,
            environment="production",
            start_time=datetime.now(UTC),
        )
        db_session.add(trace_a)
        await db_session.commit()

    # 2. Register User B and create Project B
    await register(client, EMAIL_B)
    headers_b = await headers_for(client, EMAIL_B)
    org_b = await org_id(client, headers_b)
    project_b = await create_project(client, headers_b, org_b, name="Project B")

    # 3. User B attempting to read Trace A must return 403 or 404 (AT-P8-017)
    resp = await client.get(
        f"/api/v1/observability/traces/{trace_a_id}",
        headers=headers_b,
    )
    assert resp.status_code in (403, 404), resp.text


@pytest.mark.asyncio
async def test_viewer_permission_restriction(client: AsyncClient, session_factory) -> None:
    # 1. Register Owner and create Project
    await register(client, EMAIL_A)
    headers_owner = await headers_for(client, EMAIL_A)
    org_owner = await org_id(client, headers_owner)
    project_id = await create_project(client, headers_owner, org_owner, name="Main Proj")

    # 2. Register Viewer and add to Organization as a VIEWER
    await register(client, EMAIL_VIEWER)
    headers_viewer = await headers_for(client, EMAIL_VIEWER)
    viewer_user_resp = await client.get("/api/v1/auth/me", headers=headers_viewer)
    viewer_user_id = viewer_user_resp.json()["data"]["user"]["id"]

    async with session_factory() as db_session:
        # Directly set member role to VIEWER in DB
        member = OrganizationMember(
            id=uuid4(),
            organization_id=UUID(org_owner),
            user_id=UUID(viewer_user_id),
            role=Role.VIEWER,
            created_at=datetime.now(UTC),
        )
        db_session.add(member)
        await db_session.commit()

    # 3. Create Alert Rule using Owner (should succeed)
    rule_payload = {
        "name": "Owner Rule",
        "metric": "error_rate",
        "operator": ">",
        "threshold": 0.05,
        "duration_seconds": 600,
        "cooldown_seconds": 3600,
        "severity": "WARNING",
    }
    resp_create_owner = await client.post(
        f"/api/v1/projects/{project_id}/alert-rules",
        json=rule_payload,
        headers=headers_owner,
    )
    assert resp_create_owner.status_code == 201, resp_create_owner.text
    rule_id = resp_create_owner.json()["id"]

    # 4. Create Alert Rule using Viewer (must fail with 403) (AT-P8-018)
    resp_create_viewer = await client.post(
        f"/api/v1/projects/{project_id}/alert-rules",
        json=rule_payload,
        headers=headers_viewer,
    )
    assert resp_create_viewer.status_code == 403, resp_create_viewer.text

    # 5. Patch Alert Rule using Viewer (must fail with 403)
    resp_patch_viewer = await client.patch(
        f"/api/v1/alert-rules/{rule_id}",
        json={"name": "Tampered Name"},
        headers=headers_viewer,
    )
    assert resp_patch_viewer.status_code == 403, resp_patch_viewer.text

    # 6. Delete Alert Rule using Viewer (must fail with 403)
    resp_delete_viewer = await client.delete(
        f"/api/v1/alert-rules/{rule_id}",
        headers=headers_viewer,
    )
    assert resp_delete_viewer.status_code == 403, resp_delete_viewer.text

    # 7. Viewer cannot modify observability settings (privacy/retention/sampling)
    resp_settings_viewer = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"sample_rate": 0.0, "observability_mode": "FULL_CONTENT"},
        headers=headers_viewer,
    )
    assert resp_settings_viewer.status_code == 403, resp_settings_viewer.text

    # 8. Viewer can still read observability settings
    resp_settings_viewer_get = await client.get(
        f"/api/v1/projects/{project_id}/observability/settings",
        headers=headers_viewer,
    )
    assert resp_settings_viewer_get.status_code == 200, resp_settings_viewer_get.text
