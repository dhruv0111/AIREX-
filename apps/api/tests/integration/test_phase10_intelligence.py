"""Phase 10 Intelligence & Deployment Decisions Integration Tests."""

from __future__ import annotations

from datetime import datetime, UTC
import pytest
from uuid import UUID

from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)
from app.models import Environment, Trace, AlertRule, Alert
from app.workers.tasks import TASK_REGISTRY

EMAIL = "p10_int@example.com"


async def _setup_p10(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="P10 Project", slug=f"p10-{email.split('@')[0]}"
    )

    # Create environment
    env_resp = await client.post(
        f"/api/v1/projects/{project}/environments",
        json={"name": "Production", "environment_type": "PRODUCTION"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert env_resp.status_code == 201, env_resp.text
    env_id = env_resp.json()["data"]["id"]

    # Create provider
    prov_resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local P10"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert prov_resp.status_code == 201, prov_resp.text
    provider_id = prov_resp.json()["data"]["id"]

    # Create model
    model_resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": "GPT-4o Staging",
            "model_identifier": "gpt-4o",
            "provider_id": provider_id,
            "environment_id": env_id,
            "configuration": {"temperature": 0.0},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert model_resp.status_code == 201, model_resp.text
    model_id = model_resp.json()["data"]["id"]

    return headers, org, project, env_id, provider_id, model_id


@pytest.mark.asyncio
async def test_policy_crud_lifecycle(client):
    headers, org, project, env_id, _, _ = await _setup_p10(client, "p10_policy@example.com")

    # 1. Create Policy
    create_resp = await client.post(
        f"/api/v1/projects/{project}/release-policies",
        json={
            "name": "Production Strict Policy",
            "description": "High bar release gate for enterprise tier",
            "environment_id": env_id,
            "min_reliability_score": 85.0,
            "max_regression_severity": "MEDIUM",
            "max_error_rate": 0.01,
            "max_latency_ms": 1500.0,
            "max_critical_alerts": 0,
            "required_benchmark": True,
            "required_evaluation": True,
            "max_evidence_age_days": 14,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert create_resp.status_code == 201, create_resp.text
    policy_data = create_resp.json()["data"]
    policy_id = policy_data["id"]
    assert policy_data["version"] == 1
    assert policy_data["min_reliability_score"] == 85.0

    # 2. List Policies
    list_resp = await client.get(
        f"/api/v1/projects/{project}/release-policies",
        headers={**headers, "X-Organization-Id": org},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) >= 1

    # 3. Get Policy
    get_resp = await client.get(
        f"/api/v1/projects/{project}/release-policies/{policy_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == policy_id

    # 4. Update Policy -> Version bumps to 2
    update_resp = await client.put(
        f"/api/v1/projects/{project}/release-policies/{policy_id}",
        json={"min_reliability_score": 90.0},
        headers={**headers, "X-Organization-Id": org},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["version"] == 2
    assert update_resp.json()["data"]["min_reliability_score"] == 90.0


@pytest.mark.asyncio
async def test_decision_creation_and_evaluation(client):
    headers, org, project, env_id, _, model_id = await _setup_p10(client, "p10_dec@example.com")

    # Create Policy with non-required benchmark/evaluation for initial pass
    pol_resp = await client.post(
        f"/api/v1/projects/{project}/release-policies",
        json={
            "name": "Standard Staging Policy",
            "environment_id": env_id,
            "max_critical_alerts": 0,
            "required_benchmark": False,
            "required_evaluation": False,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    policy_id = pol_resp.json()["data"]["id"]

    # 1. Create Decision (DRAFT state)
    dec_resp = await client.post(
        f"/api/v1/projects/{project}/release-decisions",
        json={
            "environment_id": env_id,
            "model_id": model_id,
            "release_policy_id": policy_id,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert dec_resp.status_code == 201, dec_resp.text
    dec_data = dec_resp.json()["data"]
    decision_id = dec_data["id"]
    assert dec_data["status"] == "DRAFT"
    assert len(dec_data["configuration_fingerprint"]) == 64

    # 2. Evaluate Decision -> APPROVED
    eval_resp = await client.post(
        f"/api/v1/projects/{project}/release-decisions/{decision_id}/evaluate",
        headers={**headers, "X-Organization-Id": org},
    )
    assert eval_resp.status_code == 200, eval_resp.text
    evaluated = eval_resp.json()["data"]
    assert evaluated["status"] == "DECIDED"
    assert evaluated["outcome"] == "APPROVED"
    assert evaluated["readiness_score"] is not None

    # 3. Check individual checks endpoint
    checks_resp = await client.get(
        f"/api/v1/projects/{project}/release-decisions/{decision_id}/checks",
        headers={**headers, "X-Organization-Id": org},
    )
    assert checks_resp.status_code == 200
    assert len(checks_resp.json()["data"]) >= 1

    # 4. Check canonical evidence endpoint
    ev_resp = await client.get(
        f"/api/v1/projects/{project}/release-decisions/{decision_id}/evidence",
        headers={**headers, "X-Organization-Id": org},
    )
    assert ev_resp.status_code == 200
    assert len(ev_resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_decision_blocked_by_critical_alert(client, session_factory):
    headers, org, project, env_id, _, model_id = await _setup_p10(client, "p10_crit@example.com")

    # Insert an active critical alert in database
    async with session_factory() as session:
        rule = AlertRule(
            project_id=UUID(project),
            name="P95 Latency Spike",
            metric="latency_p95",
            operator=">",
            threshold=2000.0,
            severity="CRITICAL",
            is_enabled=True,
        )
        session.add(rule)
        await session.flush()

        alert = Alert(
            alert_rule_id=rule.id,
            project_id=UUID(project),
            status="TRIGGERED",
            severity="CRITICAL",
            message="Severe latency spike detected",
            observed_value=4500.0,
            triggered_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        session.add(alert)
        await session.commit()

    # Create Policy
    pol_resp = await client.post(
        f"/api/v1/projects/{project}/release-policies",
        json={
            "name": "Zero Critical Alerts Policy",
            "environment_id": env_id,
            "max_critical_alerts": 0,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    policy_id = pol_resp.json()["data"]["id"]

    # Create & Evaluate Decision
    dec_resp = await client.post(
        f"/api/v1/projects/{project}/release-decisions",
        json={
            "environment_id": env_id,
            "model_id": model_id,
            "release_policy_id": policy_id,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    decision_id = dec_resp.json()["data"]["id"]

    eval_resp = await client.post(
        f"/api/v1/projects/{project}/release-decisions/{decision_id}/evaluate",
        headers={**headers, "X-Organization-Id": org},
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["data"]["outcome"] == "BLOCKED"


@pytest.mark.asyncio
async def test_decision_comparison_and_executive_overview(client):
    headers, org, project, env_id, _, model_id = await _setup_p10(client, "p10_comp@example.com")

    # Create Policy
    pol_resp = await client.post(
        f"/api/v1/projects/{project}/release-policies",
        json={
            "name": "Standard Comparison Policy",
            "environment_id": env_id,
            "max_critical_alerts": 0,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    policy_id = pol_resp.json()["data"]["id"]

    # Decision 1
    d1 = (await client.post(
        f"/api/v1/projects/{project}/release-decisions",
        json={"environment_id": env_id, "model_id": model_id, "release_policy_id": policy_id},
        headers={**headers, "X-Organization-Id": org},
    )).json()["data"]["id"]
    await client.post(f"/api/v1/projects/{project}/release-decisions/{d1}/evaluate", headers={**headers, "X-Organization-Id": org})

    # Decision 2
    d2 = (await client.post(
        f"/api/v1/projects/{project}/release-decisions",
        json={"environment_id": env_id, "model_id": model_id, "release_policy_id": policy_id},
        headers={**headers, "X-Organization-Id": org},
    )).json()["data"]["id"]
    await client.post(f"/api/v1/projects/{project}/release-decisions/{d2}/evaluate", headers={**headers, "X-Organization-Id": org})

    # Compare Decision 2 against Decision 1
    comp_resp = await client.get(
        f"/api/v1/projects/{project}/release-decisions/{d2}/compare?previous_decision_id={d1}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()["data"]
    assert comp_data["is_compatible"] is True
    assert len(comp_data["metrics"]) >= 1

    # Executive Overview
    overview_resp = await client.get(
        f"/api/v1/projects/{project}/intelligence/overview",
        headers={**headers, "X-Organization-Id": org},
    )
    assert overview_resp.status_code == 200
    overview = overview_resp.json()["data"]
    assert overview["overall_status"] in ("READY", "AT_RISK", "BLOCKED")
    assert overview["readiness_score"] is not None

    # Actions list
    actions_resp = await client.get(
        f"/api/v1/projects/{project}/intelligence/actions",
        headers={**headers, "X-Organization-Id": org},
    )
    assert actions_resp.status_code == 200
    assert len(actions_resp.json()["data"]["actions"]) >= 1
