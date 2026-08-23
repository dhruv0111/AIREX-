"""Phase 3 evaluation security tests (spec §45–§47, §62).

Covers SQL injection safety, cross-tenant isolation (org, project, model,
dataset-version), viewer restrictions, evaluation/result ID enumeration and
unauthorized cancel/run.
"""

from __future__ import annotations

import uuid

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "sec-eval@example.com"
OTHER = "sec-eval-other@example.com"
VIEWER = "sec-eval-viewer@example.com"
MODEL_IDENT = "local-sec"

DEFAULT_CFG = {
    "evaluators": [{"type": "exact_match", "enabled": True}],
    "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
}


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="Sec Eval", slug=f"sec-eval-{email.split('@')[0]}"
    )
    return headers, org, project


async def _create_env(client, headers, org, project):
    resp = await client.post(
        f"/api/v1/projects/{project}/environments",
        json={"name": "Staging", "environment_type": "STAGING"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_provider(client, headers, org):
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local Sec"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id):
    resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": MODEL_IDENT,
            "model_identifier": MODEL_IDENT,
            "provider_id": provider_id,
            "configuration": {},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_dataset_version(client, headers, org, project):
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Sec DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    up = await client.post(
        f"/api/v1/datasets/{ds.json()['data']['id']}/versions",
        files={
            "file": (
                "data.jsonl",
                b'{"input":"a","expected_output":"b"}\n',
                "application/octet-stream",
            )
        },
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert up.status_code == 201, up.text
    return up.json()["data"]["id"]


async def _setup(client, email: str = EMAIL):
    headers, org, project = await _ctx(client, email=email)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    model = await _create_model(client, headers, org, project, provider)
    version = await _create_dataset_version(client, headers, org, project)
    return headers, org, project, env, model, version


async def _create_eval(client, headers, org, project, env, model, version, configuration=None):
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": configuration or DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------- SQL injection


@pytest.mark.asyncio
async def test_sql_injection_in_status_filter_is_safe(client):
    headers, org, project, env, model, version = await _setup(client)
    await _create_eval(client, headers, org, project, env, model, version)
    listed = await client.get(
        f"/api/v1/evaluations?project_id={project}&status=COMPLETED' OR '1'='1",
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 0  # injected status matches nothing


@pytest.mark.asyncio
async def test_sql_injection_in_dataset_version_id_rejected(client):
    headers, org, project, env, model, version = await _setup(client)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": "version' OR '1'='1",
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    # Malformed UUID is rejected by validation (400/422), never reaches SQL.
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_sql_injection_in_unknown_evaluator_rejected(client):
    headers, org, project, env, model, version = await _setup(client)
    cfg = {
        "evaluators": [{"type": "exact_match' OR '1'='1", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": cfg,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400  # unknown evaluator -> validation failure


# ----------------------------------------------------------- cross-tenant isolation


@pytest.mark.asyncio
async def test_cross_tenant_evaluation_access_denied(client):
    headers, org, project, env, model, version = await _setup(client)
    run = await _create_eval(client, headers, org, project, env, model, version)

    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/evaluations/{run['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_results_denied(client):
    headers, org, project, env, model, version = await _setup(client)
    run = await _create_eval(client, headers, org, project, env, model, version)

    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/evaluations/{run['id']}/results",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_cancel_denied(client):
    headers, org, project, env, model, version = await _setup(client)
    run = await _create_eval(client, headers, org, project, env, model, version)

    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.post(
        f"/api/v1/evaluations/{run['id']}/cancel",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_org_evaluation_list_isolated(client):
    headers, org, project, env, model, version = await _setup(client)
    await _create_eval(client, headers, org, project, env, model, version)

    other_headers, other_org, other_project = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/evaluations?project_id={other_project}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 0


# ------------------------------------------------------- project/model/dataset isolation


@pytest.mark.asyncio
async def test_model_from_different_project_rejected(client):
    headers, org, project, env, model, version = await _setup(client)
    # A second project within the same org with its own model.
    project_b = await create_project(client, headers, org, name="Proj B", slug="sec-proj-b-model")
    provider_b = await _create_provider(client, headers, org)
    model_b = await _create_model(client, headers, org, project_b, provider_b)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model_b,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400  # model does not belong to this project


@pytest.mark.asyncio
async def test_dataset_version_from_different_project_rejected(client):
    headers, org, project, env, model, version = await _setup(client)
    # A second project within the same org with its own dataset version.
    project_b = await create_project(client, headers, org, name="Proj B", slug="sec-proj-b-ds")
    version_b = await _create_dataset_version(client, headers, org, project_b)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version_b,
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400  # dataset version not in this project


@pytest.mark.asyncio
async def test_environment_from_different_project_rejected(client):
    headers, org, project, env, model, version = await _setup(client)
    # A second project within the same org with its own environment.
    project_b = await create_project(client, headers, org, name="Proj B", slug="sec-proj-b-env")
    env_b = await _create_env(client, headers, org, project_b)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env_b,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400


# ------------------------------------------------------------- viewer restrictions


@pytest.mark.asyncio
async def test_viewer_can_read_but_not_mutate(client, session_factory):
    from app.evaluations.runner import EvaluationRunner

    headers, org, project, env, model, version = await _setup(client)
    run = await _create_eval(client, headers, org, project, env, model, version)
    await EvaluationRunner(session_factory).run(uuid.UUID(run["id"]))

    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)

    # Read is allowed.
    got = await client.get(
        f"/api/v1/evaluations/{run['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert got.status_code == 200
    results = await client.get(
        f"/api/v1/evaluations/{run['id']}/results",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert results.status_code == 200

    # Mutations are forbidden.
    cancel = await client.post(
        f"/api/v1/evaluations/{run['id']}/cancel",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert cancel.status_code == 403
    run_now = await client.post(
        f"/api/v1/evaluations/{run['id']}/run",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert run_now.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_create_evaluation(client):
    headers, org, project, env, model, version = await _setup(client)
    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


# ------------------------------------------------------------------- enumeration


@pytest.mark.asyncio
async def test_evaluation_id_enumeration_returns_404(client):
    headers, org, _ = await _ctx(client)
    resp = await client.get(
        f"/api/v1/evaluations/{uuid.uuid4()}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_result_mutation_from_other_org_denied(client, session_factory):
    from app.evaluations.runner import EvaluationRunner

    headers, org, project, env, model, version = await _setup(client)
    run = await _create_eval(client, headers, org, project, env, model, version)
    await EvaluationRunner(session_factory).run(uuid.UUID(run["id"]))
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    result_id = results[0]["id"]

    # A member of another org cannot mutate the result (run not visible -> 404).
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.patch(
        f"/api/v1/evaluations/{run['id']}/results/{result_id}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404

    # Even the owning org cannot mutate results (immutability -> 409).
    resp = await client.patch(
        f"/api/v1/evaluations/{run['id']}/results/{result_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409
