"""Phase 5 security tests (multi-tenant isolation, viewer read-only, ID
enumeration, unauthorized approve/reject/dataset integration, SQLi)."""

from __future__ import annotations

import json
import uuid

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "sec5@example.com"
OTHER = "sec5-other@example.com"
VIEWER = "sec5-viewer@example.com"

GEN_VALID = json.dumps(
    {
        "test_cases": [
            {
                "input": "What is 2+2?",
                "expected_output": "4",
                "category": "math",
                "difficulty": "easy",
                "generation_type": "BASIC",
            },
            {
                "input": "Capital of France?",
                "expected_output": "Paris",
                "category": "geography",
                "difficulty": "easy",
                "generation_type": "BASIC",
            },
        ]
    }
)


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="Sec5 Proj", slug=f"sec5-{email.split('@')[0]}"
    )
    return headers, org, project


async def _create_provider(client, headers, org):
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local Sec5"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id, name="generator"):
    resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": name,
            "model_identifier": name,
            "provider_id": provider_id,
            "configuration": {"local_content": GEN_VALID},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_generation(client, headers, org, project, gen_model, instruction="x"):
    resp = await client.post(
        "/api/v1/generations",
        json={
            "project_id": project,
            "source_type": "MANUAL_INSTRUCTION",
            "generation_type": "BASIC",
            "instruction": instruction,
            "count": 2,
            "configuration": {"generation_types": ["BASIC"]},
            "generator_model_id": gen_model,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _execute(session_factory, request_id):
    from app.generation.runner import GenerationRunner

    await GenerationRunner(session_factory).run(uuid.UUID(request_id))


async def _add_member(client, headers, org, email, role):
    await register(client, email)
    resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": email, "role": role},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return await headers_for(client, email)


async def _setup(client, email: str = EMAIL):
    headers, org, project = await _ctx(client, email=email)
    provider = await _create_provider(client, headers, org)
    gen_model = await _create_model(client, headers, org, project, provider)
    return headers, org, project, gen_model


async def _candidates(client, headers, org, request_id):
    resp = await client.get(
        f"/api/v1/generations/{request_id}/candidates",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ------------------------------------------------------------------ cross-tenant


@pytest.mark.asyncio
async def test_cross_tenant_generation_access_denied(client):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/generations/{request['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_candidate_access_denied(client, session_factory):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/candidates/{cases[0]['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_review_denied(client, session_factory):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.post(
        f"/api/v1/candidates/{cases[0]['id']}/review",
        json={"action": "approve"},
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_dataset_integration_denied(client, session_factory):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    await client.post(
        f"/api/v1/candidates/{cases[0]['id']}/review",
        json={"action": "approve"},
        headers={**headers, "X-Organization-Id": org},
    )
    other_headers, other_org, other_project = await _ctx(client, email=OTHER)
    ds = await client.post(
        f"/api/v1/projects/{other_project}/datasets",
        json={"name": "Other DS"},
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert ds.status_code == 201, ds.text
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": ds.json()["data"]["id"], "candidate_ids": [cases[0]["id"]]},
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404  # candidate not found in org B


@pytest.mark.asyncio
async def test_cross_tenant_generator_model_rejected(client):
    headers, org, project, gen_model = await _setup(client)
    other_headers, other_org, other_project = await _ctx(client, email=OTHER)
    resp = await client.post(
        "/api/v1/generations",
        json={
            "project_id": other_project,
            "source_type": "MANUAL_INSTRUCTION",
            "generation_type": "BASIC",
            "count": 2,
            "generator_model_id": gen_model,
        },
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 400  # model belongs to another project


# ------------------------------------------------------------------ viewer


@pytest.mark.asyncio
async def test_viewer_read_only_generation_and_candidates(client, session_factory):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    await _execute(session_factory, request["id"])
    viewer_headers = await _add_member(client, headers, org, VIEWER, "VIEWER")

    got = await client.get(
        f"/api/v1/generations/{request['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert got.status_code == 200
    cases = await _candidates(client, viewer_headers, org, request["id"])
    assert len(cases) == 2

    # Viewer cannot create/cancel/approve/reject/dataset-version.
    create = await client.post(
        "/api/v1/generations",
        json={
            "project_id": project,
            "source_type": "MANUAL_INSTRUCTION",
            "generation_type": "BASIC",
            "count": 2,
            "generator_model_id": gen_model,
        },
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert create.status_code == 403

    cancel = await client.post(
        f"/api/v1/generations/{request['id']}/cancel",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert cancel.status_code == 403

    review = await client.post(
        f"/api/v1/candidates/{cases[0]['id']}/review",
        json={"action": "approve"},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert review.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_create_dataset_version(client, session_factory):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    for case in cases:
        await client.post(
            f"/api/v1/candidates/{case['id']}/review",
            json={"action": "approve"},
            headers={**headers, "X-Organization-Id": org},
        )
    viewer_headers = await _add_member(client, headers, org, VIEWER, "VIEWER")
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    dataset_id = ds.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": dataset_id, "candidate_ids": [c["id"] for c in cases]},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


# --------------------------------------------------------------- enumeration


@pytest.mark.asyncio
async def test_generation_id_enumeration_404(client):
    headers, org, _ = await _ctx(client)
    resp = await client.get(
        f"/api/v1/generations/{uuid.uuid4()}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_candidate_id_enumeration_404(client):
    headers, org, _ = await _ctx(client)
    resp = await client.get(
        f"/api/v1/candidates/{uuid.uuid4()}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dataset_version_id_enumeration_404(client):
    headers, org, project, gen_model = await _setup(client)
    resp = await client.post(
        f"/api/v1/generations/{uuid.uuid4()}/dataset-version",
        json={"dataset_id": str(uuid.uuid4()), "candidate_ids": [str(uuid.uuid4())]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------- SQLi


@pytest.mark.asyncio
async def test_sql_injection_instruction_safe(client):
    headers, org, project, gen_model = await _setup(client)
    # _create_generation asserts 201 internally; an injected instruction must
    # still be accepted as literal data (parameterized SQL).
    await _create_generation(client, headers, org, project, gen_model, instruction="x' OR '1'='1")
    listed = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "status": "QUEUED' OR '1'='1"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200
    # SQLi in the status filter must not inject rows from other statuses.
    assert all(g["status"] == "QUEUED' OR '1'='1" for g in listed.json()["data"])


@pytest.mark.asyncio
async def test_sql_injection_source_type_safe(client):
    headers, org, project, gen_model = await _setup(client)
    await _create_generation(client, headers, org, project, gen_model)
    listed = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "source_type": "MANUAL_INSTRUCTION' OR '1'='1"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 0


# ------------------------------------------------------------------- auth


@pytest.mark.asyncio
async def test_generation_requires_auth(client):
    resp = await client.get("/api/v1/generations")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_organization_header_rejected(client):
    headers, org, project, gen_model = await _setup(client)
    resp = await client.get(
        "/api/v1/generations",
        params={"project_id": project},
        headers={**headers, "X-Organization-Id": "not-a-uuid"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_get_candidate_success(client, session_factory):
    headers, org, project, gen_model = await _setup(client)
    request = await _create_generation(client, headers, org, project, gen_model)
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    resp = await client.get(
        f"/api/v1/candidates/{cases[0]['id']}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == cases[0]["id"]
