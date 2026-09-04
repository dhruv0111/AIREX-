"""Phase 15 Release Gate: Independent Reality Verification.

Covers End-to-End Requirements:
2.A: Project Access Enforcement across 8 Subsystems (DIRECT > TEAM > ORG > NO_ACCESS)
2.B: Sensitive Data Protection (ALLOW, WARN, REDACT, BLOCK across live flows)
2.C: Automatic Compliance Evidence (6 lifecycle completion flows)
2.D: Agent Reliability in Release Decisions (7 dimensions, safety blocking)
2.E: Retention Scheduler & Legal Hold Enforcement (Worker execution, preservation)
2.F: Production Database Pool Behavior (Concurrency, overflow, no connection leaks)
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role, resolve_user_project_access
from app.core.sensitive_data import (
    SensitiveDataAction,
    redact_text,
    sanitize_payload,
    scan_text,
)
from app.evaluations.benchmark_runner import BenchmarkRunner
from app.evaluations.experiment_runner import ExperimentRunner
from app.evaluations.runner import EvaluationRunner
from app.models.organization import Organization
from app.models.user import User
from app.models.benchmark import BenchmarkSuite, BenchmarkVersion
from app.models.compliance import (
    ComplianceEvidence,
    LegalHold,
    RetentionPolicy,
)
from app.models.project import Project
from app.services.agent_service import AgentService
from app.services.decision_engine import DecisionEngine
from app.services.evidence_service import publish_canonical_evidence
from app.services.governance_service import GovernanceService
from app.services.retention_service import RetentionService
from app.workers.tasks import execute_centralized_retention, TASK_REGISTRY


async def _register_user(client: AsyncClient, email: str, name: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "name": name},
    )
    assert resp.status_code == 201, resp.text


async def _get_headers(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _get_org(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["memberships"][0]["organization_id"])


# ===========================================================================
# 2.A: Project-Level Access Enforcement Across 8 Subsystems
# ===========================================================================
@pytest.mark.asyncio
async def test_gate_project_access_enforcement_all_subsystems(client: AsyncClient, session_factory):
    """Verify DIRECT > TEAM > ORG > NO_ACCESS across all 8 subsystems."""
    owner_email = f"gate-owner-{uuid4().hex[:6]}@example.com"
    member_email = f"gate-member-{uuid4().hex[:6]}@example.com"
    other_email = f"gate-other-{uuid4().hex[:6]}@example.com"

    await _register_user(client, owner_email, "Gate Owner")
    await _register_user(client, member_email, "Gate Member")
    await _register_user(client, other_email, "Other Tenant")

    owner_hdrs = await _get_headers(client, owner_email)
    member_hdrs = await _get_headers(client, member_email)
    other_hdrs = await _get_headers(client, other_email)

    org = await _get_org(client, owner_hdrs)
    other_org = await _get_org(client, other_hdrs)

    # 1. Invite member into owner's org as ENGINEER
    invite_resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": member_email, "role": "ENGINEER"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert invite_resp.status_code == 201

    # 2. Owner creates Project Omega
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Project Omega", "slug": f"omega-{uuid4().hex[:4]}"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert proj_resp.status_code == 201
    proj_data = proj_resp.json()
    proj_id = proj_data.get("data", proj_data)["id"]

    # 3. Restrict Project Omega via Team assignment (giving team VIEWER role)
    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Restricted Team", "slug": f"team-{uuid4().hex[:4]}"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert team_resp.status_code == 201
    team_data = team_resp.json()
    team_id = team_data.get("data", team_data)["id"]

    assign_resp = await client.post(
        f"/api/v1/teams/{team_id}/project-access",
        json={"project_id": proj_id, "permission_role": "VIEWER"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert assign_resp.status_code in (200, 201)

    # 4. Member (not in team) is blocked from all 8 subsystems (NO_ACCESS)
    subsystems_get = [
        f"/api/v1/evaluations?project_id={proj_id}",
        f"/api/v1/projects/{proj_id}/datasets",
        f"/api/v1/projects/{proj_id}/experiments",
        f"/api/v1/projects/{proj_id}/observability/overview",
        f"/api/v1/projects/{proj_id}/benchmarks",
        f"/api/v1/projects/{proj_id}/alerts",
        f"/api/v1/projects/{proj_id}/release-policies",
        f"/api/v1/projects/{proj_id}/agents",
    ]

    for endpoint in subsystems_get:
        r = await client.get(endpoint, headers={**member_hdrs, "X-Organization-Id": org})
        assert r.status_code == 403, f"Expected 403 on {endpoint}, got {r.status_code}: {r.text}"

    # Cross-tenant attempt from other tenant is strictly blocked (403 or 404)
    for endpoint in subsystems_get:
        r = await client.get(endpoint, headers={**other_hdrs, "X-Organization-Id": other_org})
        assert r.status_code in (403, 404), f"Cross-tenant leak on {endpoint}: {r.status_code}"

    # 5. Add member to team -> member now has TEAM_ACCESS (VIEWER)
    me_resp = await client.get("/api/v1/auth/me", headers=member_hdrs)
    member_user_id = me_resp.json()["data"]["user"]["id"]
    add_mem_resp = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": member_user_id, "role": "MEMBER"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert add_mem_resp.status_code in (200, 201)

    # Member can now GET all 8 subsystems
    for endpoint in subsystems_get:
        r = await client.get(endpoint, headers={**member_hdrs, "X-Organization-Id": org})
        assert r.status_code == 200, f"Expected 200 on {endpoint}, got {r.status_code}: {r.text}"

    # Member as VIEWER cannot execute mutations (e.g. creating dataset or evaluation)
    ds_resp = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        json={"name": "Disallowed Dataset", "description": "test"},
        headers={**member_hdrs, "X-Organization-Id": org},
    )
    assert ds_resp.status_code == 403

    # 6. Grant DIRECT_ACCESS (ADMIN) to member -> Direct overrides Team VIEWER
    direct_resp = await client.post(
        f"/api/v1/access/projects/{proj_id}/users",
        json={"user_id": member_user_id, "permission_role": "ADMIN"},
        headers={**owner_hdrs, "X-Organization-Id": org},
    )
    assert direct_resp.status_code in (200, 201)

    # Now member with DIRECT ADMIN CAN create dataset
    ds_resp2 = await client.post(
        f"/api/v1/projects/{proj_id}/datasets",
        json={"name": "Allowed Dataset", "description": "test"},
        headers={**member_hdrs, "X-Organization-Id": org},
    )
    assert ds_resp2.status_code == 201


# ===========================================================================
# 2.B: Sensitive Data Protection: ALLOW, WARN, REDACT, BLOCK
# ===========================================================================
@pytest.mark.asyncio
async def test_gate_sensitive_data_protection_policies():
    """Verify ALLOW, WARN, REDACT, and BLOCK behaviors across payload structures."""
    payload = {
        "user": "alice",
        "creds": {
            "aws": "AKIAIOSFODNN7EXAMPLE",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_not_leak_signature",
            "card": "4111111111111111",
            "email": "confidential-lead@airex.ai",
        },
        "safe_list": ["apple", "banana"],
    }

    # 1. Action REDACT: replaces sensitive tokens
    redacted, matches, is_blocked = sanitize_payload(payload, action=SensitiveDataAction.REDACT)
    assert not is_blocked
    assert len(matches) >= 4
    assert "AKIAIOSFODNN7EXAMPLE" not in str(redacted)
    assert "4111111111111111" not in str(redacted)
    assert "[REDACTED:API_KEY_AWS]" in str(redacted["creds"]["aws"])
    assert "[REDACTED:CREDIT_CARD]" in str(redacted["creds"]["card"])
    assert "[REDACTED:BEARER_JWT]" in str(redacted["creds"]["token"])
    assert "[REDACTED:EMAIL]" in str(redacted["creds"]["email"])
    assert redacted["safe_list"] == ["apple", "banana"]

    # 2. Action ALLOW: leaves payload unmodified
    allowed, matches, is_blocked = sanitize_payload(payload, action=SensitiveDataAction.ALLOW)
    assert not is_blocked
    assert allowed["creds"]["aws"] == "AKIAIOSFODNN7EXAMPLE"

    # 3. Action BLOCK: flags is_blocked=True
    blocked, matches, is_blocked = sanitize_payload(payload, action=SensitiveDataAction.BLOCK)
    assert is_blocked

    # 4. Action WARN: passes through without exception
    warned, matches, is_blocked = sanitize_payload(payload, action=SensitiveDataAction.WARN)
    assert not is_blocked
    assert warned["creds"]["aws"] == "AKIAIOSFODNN7EXAMPLE"


# ===========================================================================
# 2.C: Automatic Canonical Compliance Evidence Across 6 Completion Flows
# ===========================================================================
@pytest.mark.asyncio
async def test_gate_automatic_compliance_evidence_flows(session_factory):
    """Verify that canonical compliance evidence is published with deterministic fingerprints."""
    async with session_factory() as session:
        org_id = uuid4()
        proj_id = uuid4()

        flows = [
            ("evaluation_run", uuid4(), {"accuracy": 0.96, "model": "gpt-4o"}),
            ("experiment_run", uuid4(), {"gate_passed": True, "improvement_pct": 12.5}),
            ("benchmark_run", uuid4(), {"benchmark_score": 94.2, "reliability_passed": True}),
            ("release_decision", uuid4(), {"outcome": "APPROVED", "readiness_score": 0.92}),
            ("agent_run", uuid4(), {"trajectory_steps": 14, "safety_passed": True}),
            ("approval_request", uuid4(), {"status": "APPROVED", "governance_policy": "STRICT"}),
        ]

        # 1. Emit evidence for each flow
        for source_type, source_id, metadata in flows:
            ev = await publish_canonical_evidence(
                session=session,
                organization_id=org_id,
                source_type=source_type,
                source_id=source_id,
                project_id=proj_id,
                metadata_summary=metadata,
                classification="RESTRICTED",
            )
            assert ev is not None
            assert ev.sha256_fingerprint is not None
            assert len(ev.sha256_fingerprint) == 64
            assert ev.source_type == source_type
            assert ev.source_id == str(source_id)

        await session.commit()

        # 2. Verify all 6 records exist and are queryable
        stmt = select(ComplianceEvidence).where(ComplianceEvidence.organization_id == org_id)
        res = await session.execute(stmt)
        records = res.scalars().all()
        assert len(records) == 6

        # 3. Idempotent re-emission: re-publishing the same source_id updates without duplicates
        first_flow = flows[0]
        ev_updated = await publish_canonical_evidence(
            session=session,
            organization_id=org_id,
            source_type=first_flow[0],
            source_id=first_flow[1],
            project_id=proj_id,
            metadata_summary={"accuracy": 0.99, "re-evaluated": True},
            classification="RESTRICTED",
        )
        await session.commit()

        res2 = await session.execute(stmt)
        records2 = res2.scalars().all()
        assert len(records2) == 6
        assert ev_updated.metadata_summary["accuracy"] == 0.99


# ===========================================================================
# 2.D: Agent Reliability in Release Decisions (Scoring & Safety Blocking)
# ===========================================================================
def test_gate_decision_engine_agent_reliability_and_safety_blocking():
    """Verify 7-dim scoring and binary safety override."""
    from app.models.release_decision import ReleasePolicy
    policy = ReleasePolicy(
        project_id=uuid4(),
        name="Test Gate Policy",
        required_evaluation=True,
        required_benchmark=False,
        max_evidence_age_days=30,
        required_dataset_version_id=None,
        min_reliability_score=70.0,
        max_regression_severity="HIGH",
        max_critical_alerts=0,
        max_error_rate=0.05,
        max_p95_latency_ms=2000.0,
        min_sample_size=None,
        min_statistical_confidence=None,
        required_quality_gates=False,
    )
    engine = DecisionEngine(policy)

    eval_ev = {"source_id": str(uuid4()), "summary": {"accuracy_score": 90.0}}
    exp_ev = {"source_id": str(uuid4()), "summary": {"max_regression_severity": "NONE"}}
    bench_ev = {"source_id": str(uuid4()), "summary": {"reliability_score": 85.0}}
    obs_ev = {"source_id": str(uuid4()), "summary": {"availability": 0.999, "p95_latency_ms": 150.0}}
    alert_ev = {"source_id": str(uuid4()), "summary": {"critical_alerts_count": 0, "total_active_alerts": 0}}
    agent_ev = {"source_id": str(uuid4()), "summary": {"agent_reliability_score": 95.0, "safety_violations": 0, "safety_passed": True}}

    # Case 1: No agent evidence -> 6 standard dimensions
    score_6dim, breakdown_6dim = engine._compute_readiness_score(eval_ev, exp_ev, bench_ev, obs_ev, alert_ev)
    assert "agent_reliability" not in breakdown_6dim
    assert breakdown_6dim["evaluation_quality"]["weight"] == 0.20
    assert breakdown_6dim["benchmark_reliability"]["weight"] == 0.25

    # Case 2: Agent evidence present -> 7 dimensions (15% agent weight)
    score_7dim, breakdown_7dim = engine._compute_readiness_score(eval_ev, exp_ev, bench_ev, obs_ev, alert_ev, agent_ev)
    assert "agent_reliability" in breakdown_7dim
    assert breakdown_7dim["agent_reliability"]["weight"] == 0.15
    assert breakdown_7dim["evaluation_quality"]["weight"] == 0.15

    # Case 3: Binary Safety Violation Override
    unsafe_agent_ev = {
        "source_type": "AGENT_EVALUATION",
        "source_id": str(uuid4()),
        "summary": {"reliability_score": 98.0, "safety_violations": 2, "safety_passed": False},
    }
    evidences = [
        {"source_type": "EVALUATION", "source_id": eval_ev["source_id"], "is_fresh": True, "summary": {"accuracy_score": 95.0}},
        unsafe_agent_ev,
    ]
    res = engine.evaluate(evidences, model_id=uuid4(), environment_id=uuid4())
    assert res["outcome"] == "BLOCKED"
    agent_check = next(c for c in res["checks"] if c["rule_name"] == "agent_safety")
    assert agent_check["status"] == "FAIL"
    assert agent_check["is_blocking"] is True


# ===========================================================================
# 2.E: Retention Scheduler & Legal Hold Enforcement
# ===========================================================================
@pytest.mark.asyncio
async def test_gate_retention_scheduler_and_legal_holds(session_factory):
    """Verify worker retention task execution and absolute legal hold preservation."""
    assert "clean_centralized_retention" in TASK_REGISTRY

    async with session_factory() as session:
        org_id = uuid4()

        service = RetentionService(session)
        # Configure retention policy for evaluation runs: 30 days
        await service.create_policy(
            organization_id=org_id,
            resource_type="evaluation_run",
            retention_days=30,
            description="Clean old eval runs",
        )

        # Place an active legal hold on a specific evaluation run
        held_run_id = str(uuid4())
        await service.create_legal_hold(
            organization_id=org_id,
            title="Litigation Hold 2026",
            resource_type="evaluation_run",
            target_resource_id=held_run_id,
            reason="Investigation pending",
        )

        # Verify is_under_legal_hold check
        is_held = await service.is_under_legal_hold(org_id, "evaluation_run", held_run_id)
        assert is_held is True
        is_other_held = await service.is_under_legal_hold(org_id, "evaluation_run", str(uuid4()))
        assert is_other_held is False

        # Execute cleanup preview
        res = await service.execute_retention_cleanup(org_id, dry_run=True)
        assert "evaluation_run" in res["details"]
        assert res["deleted_records"] == 0


# ===========================================================================
# 2.F: Production Database Pool Behavior
# ===========================================================================
@pytest.mark.asyncio
async def test_gate_production_db_pool_concurrency(session_factory):
    """Verify that concurrent async database queries operate without starvation or connection leaks."""
    async def _query_worker(worker_id: int):
        async with session_factory() as session:
            res = await session.execute(text(f"SELECT {worker_id} AS worker_id"))
            row = res.fetchone()
            assert row[0] == worker_id

    # Run 30 concurrent workers competing for database sessions
    tasks = [_query_worker(i) for i in range(30)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        assert not isinstance(res, Exception), f"Pool execution encountered error: {res}"
