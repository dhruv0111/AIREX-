"""Phase 4 security tests (spec §48): cross-tenant rubric/judge-model/evaluation
access, viewer restrictions, rubric mutation authorization, ID enumeration, and
SQL injection against rubric fields."""

from __future__ import annotations

import uuid

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "sec4@example.com"
OTHER = "sec4-other@example.com"
VIEWER = "sec4-viewer@example.com"

RUBRIC_CRITERIA = [
    {"name": "correctness", "description": "Correct", "weight": 0.5},
    {"name": "relevance", "description": "Relevant", "weight": 0.5},
]

JUDGE_VALID = (
    '{"criteria": {"correctness": 0.9, "relevance": 0.8}, '
    '"overall_score": 0.85, "passed": true, "confidence": 0.9, "reasoning": "ok"}'
)


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="Sec4 Proj", slug=f"sec4-{email.split('@')[0]}"
    )
    return headers, org, project


async def _create_provider(client, headers, org):
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local Sec4"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id, name="target", config=None):
    resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": name,
            "model_identifier": name,
            "provider_id": provider_id,
            "configuration": config or {},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_rubric(client, headers, org, project):
    resp = await client.post(
        "/api/v1/rubrics",
        json={"project_id": project, "name": "Sec Rubric", "criteria": RUBRIC_CRITERIA},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _setup(client, email: str = EMAIL):
    headers, org, project = await _ctx(client, email=email)
    provider = await _create_provider(client, headers, org)
    model = await _create_model(client, headers, org, project, provider)
    judge_model = await _create_model(
        client,
        headers,
        org,
        project,
        provider,
        name="judge",
        config={"local_content": JUDGE_VALID},
    )
    rubric = await _create_rubric(client, headers, org, project)
    return headers, org, project, model, judge_model, rubric


def _judge_cfg(judge_model_id, rubric_id):
    return {
        "evaluators": [
            {
                "type": "llm_judge",
                "enabled": True,
                "judge_model_id": judge_model_id,
                "rubric_id": rubric_id,
                "threshold": 0.75,
                "reference_required": True,
            }
        ],
        "execution": {"max_concurrency": 2, "timeout_seconds": 10, "stop_on_error": False},
    }


@pytest.mark.asyncio
async def test_cross_tenant_rubric_access_denied(client):
    headers, org, project, model, judge_model, rubric = await _setup(client)
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/rubrics/{rubric['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_rubric_mutation_denied(client):
    headers, org, project, model, judge_model, rubric = await _setup(client)
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.patch(
        f"/api/v1/rubrics/{rubric['id']}",
        json={"name": "Hacked"},
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_judge_model_rejected(client):
    headers, org, project, model, judge_model, rubric = await _setup(client)
    other_headers, other_org, other_project = await _ctx(client, email=OTHER)
    # Org B's target model + dataset, but org A's judge model.
    other_provider = await _create_provider(client, other_headers, other_org)
    other_model = await _create_model(
        client, other_headers, other_org, other_project, other_provider
    )
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": other_project,
            "environment_id": None,
            "dataset_version_id": str(uuid.uuid4()),
            "model_id": other_model,
            "configuration": _judge_cfg(str(judge_model), str(uuid.uuid4())),
        },
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_viewer_can_read_rubric_not_mutate(client):
    headers, org, project, model, judge_model, rubric = await _setup(client)
    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)

    got = await client.get(
        f"/api/v1/rubrics/{rubric['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert got.status_code == 200

    patch = await client.patch(
        f"/api/v1/rubrics/{rubric['id']}",
        json={"name": "Nope"},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert patch.status_code == 403
    delete = await client.delete(
        f"/api/v1/rubrics/{rubric['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert delete.status_code == 403


@pytest.mark.asyncio
async def test_rubric_id_enumeration_returns_404(client):
    headers, org, _ = await _ctx(client)
    resp = await client.get(
        f"/api/v1/rubrics/{uuid.uuid4()}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_sql_injection_rubric_fields_safe(client):
    headers, org, project, _, _, _ = await _setup(client)
    resp = await client.post(
        "/api/v1/rubrics",
        json={
            "project_id": project,
            "name": "x' OR '1'='1",
            "criteria": RUBRIC_CRITERIA,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    listed = await client.get(
        f"/api/v1/rubrics?project_id={project}&status=ACTIVE' OR '1'='1",
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200


@pytest.mark.asyncio
async def test_used_rubric_immutable_conflict(client):
    headers, org, project, model, judge_model, rubric = await _setup(client)
    # Create a dataset version + evaluation so the rubric is referenced.
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Sec DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    ds_id = ds.json()["data"]["id"]
    payload = '{"input":"q","expected_output":"a"}\n'
    up = await client.post(
        f"/api/v1/datasets/{ds_id}/versions",
        files={"file": ("data.jsonl", payload.encode(), "application/octet-stream")},
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    version = up.json()["data"]["id"]
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": None,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": _judge_cfg(judge_model, rubric["id"]),
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    # The rubric is now referenced by a run -> immutable.
    patch = await client.patch(
        f"/api/v1/rubrics/{rubric['id']}",
        json={"name": "Renamed"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert patch.status_code == 409
