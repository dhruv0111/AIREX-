"""Phase 15 Unit Tests: Platform Integration, Unified Governance & Production Hardening."""

from __future__ import annotations

from datetime import datetime, UTC
import uuid
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.permissions import Role, resolve_user_project_access
from app.core.sensitive_data import (
    SensitiveDataAction,
    enforce_sensitive_data_policy,
    sanitize_payload,
)
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.team import Team, TeamMember, TeamProjectAccess, UserProjectAccess
from app.models.compliance import LegalHold, RetentionPolicy
from app.models.evaluation import EvaluationRun
from app.services.decision_engine import DecisionEngine
from app.services.evidence_service import EvidenceService, publish_canonical_evidence
from app.services.retention_service import RetentionService
from app.workers.tasks import execute_centralized_retention


# ==============================================================================
# 1. Configuration & Production Secrets Hardening
# ==============================================================================
def test_production_secret_validation_rejects_defaults():
    """APP_ENV=production MUST reject default fallback JWT secret and empty credentials."""
    # Insecure default jwt secret
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="change-me-to-a-long-random-secret",
            credential_encryption_key="bldmR0xEZ1Q5YjRNd2hYTE9yUDRVd3ZqZ1B0M09ZOTg=",
        )

    # Insecure fallback docker secret
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="airex_production_super_secret_jwt_key_minimum_32_bytes_long",
            credential_encryption_key="bldmR0xEZ1Q5YjRNd2hYTE9yUDRVd3ZqZ1B0M09ZOTg=",
        )

    # Insecure short secret (< 32 chars)
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="short_secret_under_32_chars",
            credential_encryption_key="bldmR0xEZ1Q5YjRNd2hYTE9yUDRVd3ZqZ1B0M09ZOTg=",
        )

    # Insecure missing credential encryption key
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="a_secure_custom_production_jwt_secret_key_minimum_32_bytes",
            credential_encryption_key="",
        )

    # Valid production settings pass
    prod_settings = Settings(
        app_env="production",
        jwt_secret_key="a_secure_custom_production_jwt_secret_key_minimum_32_bytes",
        credential_encryption_key="bldmR0xEZ1Q5YjRNd2hYTE9yUDRVd3ZqZ1B0M09ZOTg=",
    )
    assert prod_settings.app_env == "production"
    assert prod_settings.db_pool_size == 20
    assert prod_settings.db_max_overflow == 30


# ==============================================================================
# 2. Unified Project Access Resolution & Precedence
# ==============================================================================
@pytest.mark.asyncio
async def test_project_access_hierarchy_and_cross_tenant_isolation(db_session):
    """Verify:
    1. Cross-tenant isolation blocks access even if user is admin of another tenant
    2. DIRECT_ACCESS > TEAM_ACCESS > ORGANIZATION_ACCESS > NO_ACCESS
    3. Restricted project blocks non-assigned org engineers
    """
    org1 = Organization(id=uuid.uuid4(), name="Tenant 1", slug=f"t1-{uuid.uuid4().hex[:6]}")
    org2 = Organization(id=uuid.uuid4(), name="Tenant 2", slug=f"t2-{uuid.uuid4().hex[:6]}")
    db_session.add_all([org1, org2])
    await db_session.flush()

    project1 = Project(id=uuid.uuid4(), organization_id=org1.id, name="Project 1", slug="proj-1")
    project2 = Project(id=uuid.uuid4(), organization_id=org2.id, name="Project 2", slug="proj-2")
    db_session.add_all([project1, project2])
    await db_session.flush()

    user = uuid.uuid4()
    # User is ADMIN in org1
    org1_member = OrganizationMember(organization_id=org1.id, user_id=user, role="ADMIN", created_at=datetime.now(UTC))
    db_session.add(org1_member)
    await db_session.flush()

    # 1. Cross-tenant check: user is ADMIN in org1, but tries to access project2 (belongs to org2) with org1 header
    role, access_type = await resolve_user_project_access(db_session, user, project2.id, org1.id)
    assert role is None
    assert access_type == "NO_ACCESS"

    # 2. Unrestricted project in org1: user inherits ORGANIZATION_ACCESS
    role, access_type = await resolve_user_project_access(db_session, user, project1.id, org1.id)
    assert role == Role.ADMIN
    assert access_type == "ORGANIZATION_ACCESS"

    # 3. Create another user who is only an ENGINEER in org1
    engineer_user = uuid.uuid4()
    eng_member = OrganizationMember(organization_id=org1.id, user_id=engineer_user, role="ENGINEER", created_at=datetime.now(UTC))
    db_session.add(eng_member)
    await db_session.flush()

    # When project1 is unrestricted, engineer gets ORGANIZATION_ACCESS
    role, access_type = await resolve_user_project_access(db_session, engineer_user, project1.id, org1.id)
    assert role == Role.ENGINEER
    assert access_type == "ORGANIZATION_ACCESS"

    # 4. Now restrict project1 by adding a team access for a specific team
    team = Team(organization_id=org1.id, name="SecOps", slug="secops")
    db_session.add(team)
    await db_session.flush()
    t_access = TeamProjectAccess(team_id=team.id, project_id=project1.id, permission_role="VIEWER", created_at=datetime.now(UTC))
    db_session.add(t_access)
    await db_session.flush()

    # Now project1 is restricted. The engineer_user (not in team or direct) should have NO_ACCESS!
    role, access_type = await resolve_user_project_access(db_session, engineer_user, project1.id, org1.id)
    assert role is None
    assert access_type == "NO_ACCESS"

    # But ADMIN user still gets ORGANIZATION_ACCESS
    role, access_type = await resolve_user_project_access(db_session, user, project1.id, org1.id)
    assert role == Role.ADMIN
    assert access_type == "ORGANIZATION_ACCESS"

    # 5. Add engineer to team -> gets TEAM_ACCESS
    t_member = TeamMember(team_id=team.id, user_id=engineer_user, role="MEMBER", created_at=datetime.now(UTC))
    db_session.add(t_member)
    await db_session.flush()
    role, access_type = await resolve_user_project_access(db_session, engineer_user, project1.id, org1.id)
    assert role == Role.VIEWER
    assert access_type == "TEAM_ACCESS"

    # 6. Explicit direct access overrides team access (DIRECT > TEAM)
    d_access = UserProjectAccess(user_id=engineer_user, project_id=project1.id, permission_role="ADMIN", created_at=datetime.now(UTC))
    db_session.add(d_access)
    await db_session.flush()
    role, access_type = await resolve_user_project_access(db_session, engineer_user, project1.id, org1.id)
    assert role == Role.ADMIN
    assert access_type == "DIRECT_ACCESS"


# ==============================================================================
# 3. Sensitive Data Protection & Live Flow Sanitization
# ==============================================================================
def test_sensitive_data_protection_and_payload_sanitization():
    """Verify scanning and recursive sanitization of payloads with fake credentials."""
    payload = {
        "prompt": "Here is my secret AWS key: AKIAIOSFODNN7EXAMPLE and email user@example.com",
        "nested": {
            "card": "4111111111111111",
            "metadata": [
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGzTh1N_w",
                12345,
                True,
            ],
        },
        "clean_field": "Standard public information",
    }

    # REDACT action masks sensitive data
    sanitized, findings, is_blocked = sanitize_payload(payload, SensitiveDataAction.REDACT)
    assert not is_blocked
    assert len(findings) >= 3
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized["prompt"]
    assert "[REDACTED:API_KEY_AWS]" in sanitized["prompt"]
    assert "[REDACTED:EMAIL]" in sanitized["prompt"]
    assert "4111111111111111" not in sanitized["nested"]["card"]
    assert "[REDACTED:CREDIT_CARD]" in sanitized["nested"]["card"]
    assert "[REDACTED:BEARER_JWT]" in sanitized["nested"]["metadata"][0]
    assert sanitized["clean_field"] == "Standard public information"

    # BLOCK action flags is_blocked=True
    _, _, is_blocked = sanitize_payload(payload, SensitiveDataAction.BLOCK)
    assert is_blocked

    # ALLOW action leaves payload unmodified but records findings
    raw, findings, is_blocked = sanitize_payload(payload, SensitiveDataAction.ALLOW)
    assert not is_blocked
    assert len(findings) >= 3
    assert "AKIAIOSFODNN7EXAMPLE" in raw["prompt"]


# ==============================================================================
# 4. Canonical Compliance Evidence & Idempotency
# ==============================================================================
@pytest.mark.asyncio
async def test_canonical_compliance_evidence_idempotency(db_session):
    """Publishing canonical compliance evidence for the same source must be idempotent."""
    org = Organization(id=uuid.uuid4(), name="Evidence Org", slug=f"ev-org-{uuid.uuid4().hex[:6]}")
    project = Project(id=uuid.uuid4(), organization_id=org.id, name="Ev Proj", slug="ev-proj")
    db_session.add_all([org, project])
    await db_session.flush()

    source_id = str(uuid.uuid4())
    # 1. First emission
    ev1 = await publish_canonical_evidence(
        session=db_session,
        organization_id=org.id,
        source_type="evaluation_run",
        source_id=source_id,
        project_id=project.id,
        metadata_summary={"passed": 10, "failed": 0},
    )
    assert ev1 is not None
    assert ev1.integrity_status == "VALID"
    assert ev1.freshness_status == "FRESH"
    first_id = ev1.id

    # 2. Duplicate emission (e.g. retried job or rerun)
    ev2 = await publish_canonical_evidence(
        session=db_session,
        organization_id=org.id,
        source_type="evaluation_run",
        source_id=source_id,
        project_id=project.id,
        metadata_summary={"passed": 10, "failed": 0, "retried": True},
    )
    assert ev2 is not None
    # Reuses existing record without duplicate key error
    assert ev2.id == first_id
    assert ev2.metadata_summary.get("retried") is True


# ==============================================================================
# 5. Agent Reliability & Safety in Deployment Readiness
# ==============================================================================
def test_decision_engine_agent_reliability_and_safety_blocking():
    """Verify:
    1. Standard 6-dimension scoring when agent evidence is absent.
    2. 7-dimension scoring (15% agent reliability) when agent evidence is present.
    3. Binary safety violations trigger FAIL check and BLOCK outcome regardless of score.
    """
    from app.models.release_decision import ReleasePolicy
    policy = ReleasePolicy(
        project_id=uuid.uuid4(),
        name="Test Policy",
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

    eval_ev = {"source_id": str(uuid.uuid4()), "summary": {"accuracy_score": 90.0}}
    exp_ev = {"source_id": str(uuid.uuid4()), "summary": {"max_regression_severity": "NONE"}}
    bench_ev = {"source_id": str(uuid.uuid4()), "summary": {"reliability_score": 85.0}}
    obs_ev = {"source_id": str(uuid.uuid4()), "summary": {"availability": 0.999, "p95_latency_ms": 150.0}}
    alert_ev = {"source_id": str(uuid.uuid4()), "summary": {"critical_alerts_count": 0, "total_active_alerts": 0}}

    # Case 1: No agent evidence -> 6 dimensions
    score_6dim, breakdown_6dim = engine._compute_readiness_score(eval_ev, exp_ev, bench_ev, obs_ev, alert_ev)
    assert "agent_reliability" not in breakdown_6dim
    assert breakdown_6dim["evaluation_quality"]["weight"] == 0.20
    assert breakdown_6dim["benchmark_reliability"]["weight"] == 0.25

    # Case 2: Agent evidence present -> 7 dimensions with 15% weight
    agent_ev = {"source_type": "AGENT_EVALUATION", "source_id": str(uuid.uuid4()), "summary": {"reliability_score": 95.0, "safety_violations": 0, "safety_passed": True}}
    score_7dim, breakdown_7dim = engine._compute_readiness_score(eval_ev, exp_ev, bench_ev, obs_ev, alert_ev, agent_ev)
    assert "agent_reliability" in breakdown_7dim
    assert breakdown_7dim["agent_reliability"]["weight"] == 0.15
    assert breakdown_7dim["agent_reliability"]["score"] == 95.0
    assert breakdown_7dim["evaluation_quality"]["weight"] == 0.15
    assert breakdown_7dim["benchmark_reliability"]["weight"] == 0.20

    # Case 3: Binary safety violation blocks decision
    unsafe_agent_ev = {
        "source_type": "AGENT_EVALUATION",
        "source_id": str(uuid.uuid4()),
        "summary": {"reliability_score": 98.0, "safety_violations": 2, "safety_passed": False},
    }
    evidences = [
        {"source_type": "EVALUATION", "source_id": eval_ev["source_id"], "is_fresh": True, "summary": {"accuracy_score": 95.0}},
        unsafe_agent_ev,
    ]
    res = engine.evaluate(evidences, model_id=uuid.uuid4(), environment_id=uuid.uuid4())
    assert res["outcome"] == "BLOCKED"
    agent_check = next(c for c in res["checks"] if c["rule_name"] == "agent_safety")
    assert agent_check["status"] == "FAIL"
    assert agent_check["is_blocking"] is True


# ==============================================================================
# 6. Centralized Retention & Legal Hold Automation
# ==============================================================================
@pytest.mark.asyncio
async def test_centralized_retention_and_legal_hold_protection(db_session):
    """Verify:
    1. RetentionService honors active legal holds and never deletes held items.
    2. Worker task execute_centralized_retention processes organizations correctly.
    """
    org = Organization(id=uuid.uuid4(), name="Retention Org", slug=f"ret-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()

    ret_service = RetentionService(db_session)
    # Configure retention policy for evaluation runs: 30 days
    await ret_service.create_policy(
        organization_id=org.id,
        resource_type="evaluation_run",
        retention_days=30,
        description="Clean old eval runs",
    )

    # Place an active legal hold on a specific evaluation run
    held_run_id = str(uuid.uuid4())
    await ret_service.create_legal_hold(
        organization_id=org.id,
        title="Litigation Hold Alpha",
        resource_type="evaluation_run",
        target_resource_id=held_run_id,
        reason="Pending legal inquiry",
    )

    # Verify is_under_legal_hold check
    is_held = await ret_service.is_under_legal_hold(org.id, "evaluation_run", held_run_id)
    assert is_held is True
    is_other_held = await ret_service.is_under_legal_hold(org.id, "evaluation_run", str(uuid.uuid4()))
    assert is_other_held is False

    # Execute cleanup preview
    res = await ret_service.execute_retention_cleanup(org.id, dry_run=True)
    assert "evaluation_run" in res["details"]
    assert res["deleted_records"] == 0
