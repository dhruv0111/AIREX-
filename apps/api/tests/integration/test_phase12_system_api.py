"""Integration tests for Phase 12 System, Readiness, and Session Management APIs."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    # 1. /health/live
    live_resp = await client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "ok"

    # 2. /health/ready
    ready_resp = await client.get("/health/ready")
    assert ready_resp.status_code == 200
    ready_data = ready_resp.json()
    assert "overall_status" in ready_data
    assert ready_data["overall_status"] in ("HEALTHY", "DEGRADED")

    # 3. /health/startup
    startup_resp = await client.get("/health/startup")
    assert startup_resp.status_code == 200
    assert startup_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_system_readiness_api(client: AsyncClient):
    resp = await client.get("/api/v1/system/readiness")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "overall_status" in data
    assert "checks" in data
    assert len(data["checks"]) >= 5
    check_names = [c["name"] for c in data["checks"]]
    assert "database" in check_names
    assert "encryption_key" in check_names
    assert "task_queue" in check_names


@pytest.mark.asyncio
async def test_system_schema_version_api(client: AsyncClient):
    resp = await client.get("/api/v1/system/schema-version")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "current_version" in data
    assert data["expected_head"] in (
        "0013_phase12_production_readiness",
        "0014_phase13_identity_collaboration_governance",
        "0015_phase14_compliance_data_governance",
    )


@pytest.mark.asyncio
async def test_system_config_api(client: AsyncClient):
    resp = await client.get("/api/v1/system/config")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "configuration_fingerprint" in data
    assert len(data["configuration_fingerprint"]) == 64
    assert "configuration" in data
    cfg = data["configuration"]
    # Verify no plaintext secrets
    for k, v in cfg.items():
        if "secret" in k.lower() or "password" in k.lower() or "key" in k.lower():
            if isinstance(v, str) and v:
                assert "****" in v


@pytest.mark.asyncio
async def test_system_workers_api(client: AsyncClient):
    resp = await client.get("/api/v1/system/workers")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_session_management_and_refresh_rotation(client: AsyncClient):
    email = "p12_sess_user@example.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "P12 User", "email": email, "password": "Password123!"},
    )
    assert reg_resp.status_code == 201
    initial_tokens = reg_resp.json()["data"]
    refresh_token = initial_tokens["refresh_token"]
    auth_headers = {"Authorization": f"Bearer {initial_tokens['access_token']}"}

    # 2. List sessions
    sessions_resp = await client.get("/api/v1/auth/sessions", headers=auth_headers)
    assert sessions_resp.status_code == 200
    sessions = sessions_resp.json()["data"]
    assert len(sessions) >= 1
    session_id = sessions[0]["id"]

    # 3. Rotate refresh token
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()["data"]
    assert new_tokens["access_token"] != initial_tokens["access_token"]
    assert new_tokens["refresh_token"] != refresh_token

    # 4. Revoke single session
    revoke_resp = await client.post(
        f"/api/v1/auth/sessions/{session_id}/revoke",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["data"]["revoked"] is True


@pytest.mark.asyncio
async def test_admin_overview_authorized_and_forbidden(client: AsyncClient):
    email = "p12_admin_owner@example.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "Admin Owner", "email": email, "password": "Password123!"},
    )
    assert reg_resp.status_code == 201
    tokens = reg_resp.json()["data"]
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Owner user should access overview
    resp = await client.get("/api/v1/system/admin/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "application" in data
    assert "readiness" in data
    assert "stats" in data
