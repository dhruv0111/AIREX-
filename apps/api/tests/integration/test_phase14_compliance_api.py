"""Integration tests for Phase 14 Compliance, Audit Intelligence & Data Governance APIs."""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_compliance_framework_lifecycle_and_immutability(auth_client: AsyncClient):
    # 1. List frameworks (initially empty or default)
    res = await auth_client.get("/api/v1/compliance/frameworks")
    assert res.status_code == 200

    # 2. Create framework
    create_res = await auth_client.post(
        "/api/v1/compliance/frameworks",
        json={"name": "SOC2_READINESS", "description": "SOC 2 Type II readiness control set"},
    )
    assert create_res.status_code == 201
    fw = create_res.json()
    fw_id = fw["id"]
    assert fw["name"] == "SOC2_READINESS"
    assert fw["version"] == 1
    assert fw["status"] == "DRAFT"
    assert fw["is_immutable"] is False

    # 3. Add control while DRAFT
    ctrl_res = await auth_client.post(
        f"/api/v1/compliance/frameworks/{fw_id}/controls",
        json={
            "control_id": "CC-01",
            "title": "Centralized Cryptographic Secret Protection",
            "category": "DATA_PROTECTION",
            "risk_level": "CRITICAL",
            "required_evidence_types": ["SystemReadiness"],
        },
    )
    assert ctrl_res.status_code == 201
    assert ctrl_res.json()["control_id"] == "CC-01"

    # 4. Activate framework (locks version as immutable)
    act_res = await auth_client.post(f"/api/v1/compliance/frameworks/{fw_id}/activate")
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "ACTIVE"
    assert act_res.json()["is_immutable"] is True

    # 5. Adding new control to active immutable framework MUST be rejected
    reject_res = await auth_client.post(
        f"/api/v1/compliance/frameworks/{fw_id}/controls",
        json={"control_id": "CC-02", "title": "Access Control Logging"},
    )
    assert reject_res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_canonical_evidence_registry_and_verification(auth_client: AsyncClient):
    # 1. Record canonical evidence
    rec_res = await auth_client.post(
        "/api/v1/compliance/evidence",
        json={
            "source_type": "SystemReadiness",
            "source_id": str(uuid.uuid4()),
            "data_classification": "CONFIDENTIAL",
            "validity_window_days": 60,
            "metadata_summary": {"module": "encryption_probe", "status": "HEALTHY"},
        },
    )
    assert rec_res.status_code == 201
    ev = rec_res.json()
    ev_id = ev["id"]
    assert len(ev["sha256_fingerprint"]) == 64
    assert ev["data_classification"] == "CONFIDENTIAL"
    assert ev["freshness_status"] == "FRESH"
    assert ev["integrity_status"] == "VALID"

    # 2. Verify evidence
    ver_res = await auth_client.post(f"/api/v1/compliance/evidence/{ev_id}/verify")
    assert ver_res.status_code == 200
    ver_data = ver_res.json()
    assert ver_data["integrity_status"] == "VALID"
    assert ver_data["freshness_status"] == "FRESH"


@pytest.mark.asyncio
async def test_compliance_assessment_and_remediations_lifecycle(auth_client: AsyncClient):
    # Setup framework with 2 controls: one passing (ENC-01), one missing required evidence (AUD-01)
    fw_res = await auth_client.post(
        "/api/v1/compliance/frameworks",
        json={"name": "INTERNAL_GUARDRAILS", "description": "Internal AI Reliability Policy"},
    )
    fw_id = fw_res.json()["id"]

    await auth_client.post(
        f"/api/v1/compliance/frameworks/{fw_id}/controls",
        json={
            "control_id": "ENC-01",
            "title": "Encryption Key Operational",
            "category": "DATA_PROTECTION",
            "risk_level": "CRITICAL",
        },
    )
    await auth_client.post(
        f"/api/v1/compliance/frameworks/{fw_id}/controls",
        json={
            "control_id": "AUD-01",
            "title": "Multi-Tenant Access Review",
            "category": "GOVERNANCE",
            "risk_level": "HIGH",
            "required_evidence_types": ["AccessReview"],
        },
    )

    # Create assessment
    ass_res = await auth_client.post(
        "/api/v1/compliance/assessments",
        json={"framework_id": fw_id, "title": "Q3 2026 AI Reliability Audit"},
    )
    assert ass_res.status_code == 201
    ass_id = ass_res.json()["id"]

    # Run assessment
    run_res = await auth_client.post(f"/api/v1/compliance/assessments/{ass_id}/run")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "READY_FOR_REVIEW"
    assert run_data["summary"]["total_controls"] == 2
    # At least AUD-01 should be missing evidence and flagged as a gap
    assert run_data["summary"]["gaps"] >= 1

    # Verify remediation auto-generated for AUD-01
    rems_res = await auth_client.get("/api/v1/compliance/remediations")
    assert rems_res.status_code == 200
    rems = rems_res.json()
    assert len(rems) >= 1
    target_rem = rems[0]

    # Resolve remediation
    res_res = await auth_client.post(
        f"/api/v1/compliance/remediations/{target_rem['id']}/resolve",
        json={"resolution_notes": "Conducted annual access review campaign."},
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"

    # Approve assessment
    app_res = await auth_client.post(
        f"/api/v1/compliance/assessments/{ass_id}/action",
        json={"action": "APPROVE", "comment": "Verified by Chief Compliance Officer"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_retention_policy_and_legal_hold_protection(auth_client: AsyncClient):
    # 1. Create retention policy
    pol_res = await auth_client.post(
        "/api/v1/compliance/retention",
        json={"resource_type": "traces", "retention_days": 30, "description": "Retain traces for 30 days"},
    )
    assert pol_res.status_code == 201
    assert pol_res.json()["resource_type"] == "traces"
    assert pol_res.json()["retention_days"] == 30

    # 2. Place legal hold
    hold_res = await auth_client.post(
        "/api/v1/compliance/legal-holds",
        json={
            "title": "Subpoena 2026-X Investigation",
            "resource_type": "traces",
            "target_resource_id": "*",
            "reason": "Preserve all traces pending litigation",
        },
    )
    assert hold_res.status_code == 201
    hold_id = hold_res.json()["id"]
    assert hold_res.json()["is_active"] is True

    # 3. Dry-run retention cleanup (legal hold must protect records)
    clean_res = await auth_client.post(
        "/api/v1/compliance/retention/cleanup",
        json={"dry_run": True, "resource_types": ["traces"]},
    )
    assert clean_res.status_code == 200
    clean_data = clean_res.json()
    assert clean_data["dry_run"] is True

    # 4. Release legal hold
    rel_res = await auth_client.post(f"/api/v1/compliance/legal-holds/{hold_id}/release")
    assert rel_res.status_code == 200
    assert rel_res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_audit_intelligence_timeline_and_report_export(auth_client: AsyncClient):
    # 1. Query unified audit timeline
    timeline_res = await auth_client.get("/api/v1/compliance/audit/timeline?limit=20")
    assert timeline_res.status_code == 200
    t_data = timeline_res.json()
    assert "total_events" in t_data
    assert isinstance(t_data["events"], list)

    # 2. Export assessment report
    # Create and run quick assessment to export
    fw_res = await auth_client.post(
        "/api/v1/compliance/frameworks",
        json={"name": "EXPORT_TEST_FW", "description": "Report Export Framework"},
    )
    fw_id = fw_res.json()["id"]

    ass_res = await auth_client.post(
        "/api/v1/compliance/assessments",
        json={"framework_id": fw_id, "title": "Export Audit Assessment"},
    )
    ass_id = ass_res.json()["id"]
    await auth_client.post(f"/api/v1/compliance/assessments/{ass_id}/run")

    # Export JSON
    json_rep = await auth_client.get(f"/api/v1/compliance/reports/export?assessment_id={ass_id}&format=json")
    assert json_rep.status_code == 200
    assert json_rep.headers["content-type"].startswith("application/json")
    rep_obj = json_rep.json()
    assert rep_obj["framework_name"] == "EXPORT_TEST_FW"

    # Export CSV
    csv_rep = await auth_client.get(f"/api/v1/compliance/reports/export?assessment_id={ass_id}&format=csv")
    assert csv_rep.status_code == 200
    assert csv_rep.headers["content-type"].startswith("text/csv")
    assert "Control ID,Title" in csv_rep.text
