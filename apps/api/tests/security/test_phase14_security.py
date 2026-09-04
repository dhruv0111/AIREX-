"""Security and negative tests for Phase 14 Compliance, Audit Intelligence & Data Governance."""

from __future__ import annotations

import uuid
from datetime import datetime, UTC
import pytest
from httpx import AsyncClient

from app.models.organization import Organization, OrganizationMember
from app.models.compliance import ComplianceEvidence
from app.services.evidence_service import EvidenceService


@pytest.mark.asyncio
async def test_cross_tenant_compliance_isolation(client: AsyncClient, auth_client: AsyncClient):
    # Org A (via auth_client) creates a compliance framework
    res_a = await auth_client.post(
        "/api/v1/compliance/frameworks",
        json={"name": "TENANT_A_PRIVACY", "description": "Tenant A Exclusive Policy"},
    )
    assert res_a.status_code == 201
    fw_a_id = res_a.json()["id"]

    # Register Tenant B
    unique_email = f"tenant_b_{uuid.uuid4().hex[:8]}@example.com"
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "name": "Tenant B User", "password": "StrongPassword123!"},
    )
    assert reg_b.status_code == 201
    tokens_b = reg_b.json()["data"]

    # Create Org B
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}
    org_b_res = await client.post("/api/v1/organizations", json={"name": "Organization B"}, headers=headers_b)
    org_b_id = org_b_res.json()["data"]["id"]
    headers_b["X-Organization-Id"] = org_b_id

    # Tenant B attempts to access Org A's framework -> 404 Not Found
    get_res = await client.get(f"/api/v1/compliance/frameworks/{fw_a_id}/controls", headers=headers_b)
    assert get_res.status_code == 404

    # Tenant B attempts to activate Org A's framework -> 404 Not Found
    act_res = await client.post(f"/api/v1/compliance/frameworks/{fw_a_id}/activate", headers=headers_b)
    assert act_res.status_code == 404


@pytest.mark.asyncio
async def test_viewer_write_restriction(client: AsyncClient, auth_client: AsyncClient, db_session):
    # Get Org A id from auth_client me
    me_a = await auth_client.get("/api/v1/auth/me")
    org_id = me_a.headers.get("X-Organization-Id") or (await auth_client.get("/api/v1/organizations")).json()["data"][0]["id"]

    # Register Viewer User
    unique_email = f"viewer_{uuid.uuid4().hex[:8]}@example.com"
    reg_v = await client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "name": "Viewer User", "password": "StrongPassword123!"},
    )
    tokens_v = reg_v.json()["data"]
    me_v = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens_v['access_token']}"})
    viewer_user_id = me_v.json()["data"]["user"]["id"]

    # Add as VIEWER to Org A
    mem_v = OrganizationMember(
        organization_id=uuid.UUID(org_id),
        user_id=uuid.UUID(viewer_user_id),
        role="VIEWER",
        created_at=datetime.now(UTC),
    )
    db_session.add(mem_v)
    await db_session.commit()

    viewer_headers = {
        "Authorization": f"Bearer {tokens_v['access_token']}",
        "X-Organization-Id": org_id,
    }

    # VIEWER can read frameworks
    read_res = await client.get("/api/v1/compliance/frameworks", headers=viewer_headers)
    assert read_res.status_code == 200

    # VIEWER write attempts MUST be rejected with HTTP 403 Forbidden
    fw_res = await client.post(
        "/api/v1/compliance/frameworks",
        json={"name": "VIEWER_FORBIDDEN_FW"},
        headers=viewer_headers,
    )
    assert fw_res.status_code == 403

    hold_res = await client.post(
        "/api/v1/compliance/legal-holds",
        json={"title": "Unauthorized Hold", "resource_type": "traces", "target_resource_id": "*"},
        headers=viewer_headers,
    )
    assert hold_res.status_code == 403


@pytest.mark.asyncio
async def test_evidence_tampering_detection(auth_client: AsyncClient, db_session):
    # 1. Record evidence
    rec_res = await auth_client.post(
        "/api/v1/compliance/evidence",
        json={
            "source_type": "SystemReadiness",
            "source_id": "diagnostic_probe_01",
            "metadata_summary": {"probe": "db_connectivity", "latency_ms": 4.2},
        },
    )
    assert rec_res.status_code == 201
    ev_id = rec_res.json()["id"]

    # 2. Directly tamper with the metadata_summary in the database
    ev = await db_session.get(ComplianceEvidence, uuid.UUID(ev_id))
    ev.metadata_summary = {"probe": "db_connectivity", "latency_ms": 9999.9}  # Tampered payload!
    await db_session.commit()

    # 3. Verification must catch the discrepancy and mark TAMPERED
    ver_res = await auth_client.post(f"/api/v1/compliance/evidence/{ev_id}/verify")
    assert ver_res.status_code == 200
    assert ver_res.json()["integrity_status"] == "TAMPERED"


@pytest.mark.asyncio
async def test_sensitive_data_inspection_endpoint(auth_client: AsyncClient):
    payload = {
        "text": "Deployment secret is sk-proj-12345678901234567890 and email is admin@airex.ai",
        "action": "BLOCK",
    }
    res = await auth_client.post("/api/v1/compliance/sensitive-data/inspect", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_blocked"] is True
    assert len(data["findings"]) >= 2

    # REDACT action
    payload["action"] = "REDACT"
    res_redact = await auth_client.post("/api/v1/compliance/sensitive-data/inspect", json=payload)
    assert res_redact.status_code == 200
    red_data = res_redact.json()
    assert red_data["is_blocked"] is False
    assert "sk-proj-12345678901234567890" not in red_data["output_text"]
    assert "[REDACTED:" in red_data["output_text"]
