"""Phase 15 Integration Tests: End-to-End Platform Integration, Unified Governance & Hardening."""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient

from tests.integration._helpers import create_project, headers_for, org_id, register


@pytest.mark.asyncio
async def test_unified_project_access_enforcement_end_to_end(client: AsyncClient):
    """End-to-End validation of unified project access across API boundaries:
    - Restricted project blocks non-member engineers (403).
    - Team VIEWER role allows GET, blocks POST mutations (403).
    - Direct ADMIN role allows POST mutations (201).
    - Cross-tenant project access is strictly forbidden (403).
    """
    owner_email = f"owner-{uuid.uuid4().hex[:6]}@example.com"
    member_email = f"member-{uuid.uuid4().hex[:6]}@example.com"
    other_tenant_email = f"other-{uuid.uuid4().hex[:6]}@example.com"

    await register(client, owner_email, "Org Owner")
    await register(client, member_email, "Org Member")
    await register(client, other_tenant_email, "Other Tenant")

    owner_hdrs = await headers_for(client, owner_email)
    member_hdrs = await headers_for(client, member_email)
    other_hdrs = await headers_for(client, other_tenant_email)

    org = await org_id(client, owner_hdrs)
    other_org = await org_id(client, other_hdrs)

    # 1. Invite member_email into owner's org as ENGINEER
    invite_resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": member_email, "role": "ENGINEER"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert invite_resp.status_code == 201, invite_resp.text

    # 2. Owner creates Project Alpha
    proj_a = await create_project(client, owner_hdrs, org, name="Project Alpha")

    # 3. Restrict Project Alpha by assigning a Team (so unassigned org members get NO_ACCESS)
    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Core Team", "slug": f"core-{uuid.uuid4().hex[:4]}"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert team_resp.status_code == 201, team_resp.text
    team_data = team_resp.json()
    team_id = team_data.get("data", team_data)["id"]

    # Assign team to Project Alpha with VIEWER role
    assign_resp = await client.post(
        f"/api/v1/teams/{team_id}/project-access",
        json={"project_id": proj_a, "permission_role": "VIEWER"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert assign_resp.status_code in (200, 201), assign_resp.text

    # 4. member_email (not yet in team) attempts to query evaluations for Project Alpha -> 403 Forbidden
    list_evals_resp = await client.get(
        f"/api/v1/evaluations?project_id={proj_a}",
        headers={**member_hdrs, "X-Organization-Id": org},
    )
    assert list_evals_resp.status_code == 403, list_evals_resp.text

    # 5. Add member_email to the team -> member now has VIEWER access via Team
    me_resp = await client.get("/api/v1/auth/me", headers=member_hdrs)
    member_user_id = me_resp.json()["data"]["user"]["id"]
    add_member_resp = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": member_user_id, "role": "MEMBER"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert add_member_resp.status_code in (200, 201), add_member_resp.text

    # Now member CAN view evaluations
    list_evals_resp2 = await client.get(
        f"/api/v1/evaluations?project_id={proj_a}",
        headers={**member_hdrs, "X-Organization-Id": org},
    )
    assert list_evals_resp2.status_code == 200, list_evals_resp2.text

    # But member CANNOT start an evaluation (VIEWER lacks write capability) -> 403 Forbidden
    create_eval_resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": proj_a,
            "name": "Eval Should Fail",
            "model_id": str(uuid.uuid4()),
            "dataset_version_id": str(uuid.uuid4()),
            "configuration": {
                "evaluators": [
                    {"type": "exact_match", "config": {"case_sensitive": True}}
                ]
            },
        },
        headers={**member_hdrs, "X-Organization-Id": org},
    )
    assert create_eval_resp.status_code == 403, create_eval_resp.text

    # 6. Cross-Tenant Attempt: other_tenant_email attempts to read Project Alpha -> 403 Forbidden or 404 Not Found
    cross_tenant_resp = await client.get(
        f"/api/v1/evaluations?project_id={proj_a}",
        headers={**other_hdrs, "X-Organization-Id": other_org},
    )
    assert cross_tenant_resp.status_code in (403, 404), cross_tenant_resp.text


@pytest.mark.asyncio
async def test_sensitive_data_protection_in_observability_ingestion(client: AsyncClient, session_factory):
    """Verify that live ingestion of spans automatically masks credentials."""
    from datetime import datetime, UTC
    from uuid import UUID
    from app.services.observability import ObservabilityService

    owner_email = f"obs-{uuid.uuid4().hex[:6]}@example.com"
    await register(client, owner_email, "Obs User")
    hdrs = await headers_for(client, owner_email)
    org = await org_id(client, hdrs)
    proj = await create_project(client, hdrs, org, name="Obs Project")

    # Ingest trace with span containing fake AWS key and Credit Card number
    trace_id = str(uuid.uuid4())
    span_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "traces": [
            {
                "trace_id": trace_id,
                "operation_name": "User Checkout",
                "start_time": now_iso,
                "metadata": {"user_email": "customer@example.com"},
            }
        ],
        "spans": [
            {
                "span_id": span_id,
                "trace_id": trace_id,
                "name": "Process Payment",
                "span_type": "LLM",
                "start_time": now_iso,
                "attributes": {
                    "aws_secret": "AKIAIOSFODNN7EXAMPLE",
                    "card_num": "4111111111111111",
                    "note": "Public transaction note",
                },
                "status": "SUCCESS",
            }
        ],
    }

    # Ingest via service directly inside test session
    async with session_factory() as session:
        service = ObservabilityService(session)
        result = await service.ingest_batch(
            project_id=UUID(proj),
            org_id=UUID(org),
            traces=payload["traces"],
            spans=payload["spans"],
        )
        assert result["traces_ingested"] == 1
        assert result["spans_ingested"] == 1

    # Fetch trace detail via API and verify sensitive attributes were redacted
    trace_resp = await client.get(
        f"/api/v1/observability/traces/{trace_id}?project_id={proj}",
        headers={**hdrs, "X-Organization-Id": org},
    )
    assert trace_resp.status_code == 200, trace_resp.text
    trace_data = trace_resp.json()
    spans = trace_data.get("spans", [])
    assert len(spans) >= 1
    span = spans[0]
    attrs = span.get("attributes", {})
    assert "AKIAIOSFODNN7EXAMPLE" not in str(attrs)
    assert "4111111111111111" not in str(attrs)
    assert "[REDACTED:API_KEY_AWS]" in str(attrs)
    assert "[REDACTED:CREDIT_CARD]" in str(attrs)
