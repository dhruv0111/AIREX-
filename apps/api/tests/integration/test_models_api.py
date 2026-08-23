"""Model API tests (AT-P1-007..015, 029)."""

from __future__ import annotations

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

OWNER = "modelowner@example.com"
ENGINEER = "modelengineer@example.com"
VIEWER = "modelviewer@example.com"


async def _owner_ctx(client):
    await register(client, OWNER)
    headers = await headers_for(client, OWNER)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name="Model Proj", slug="model-proj")
    provider = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local", "configuration": {"latency_ms": 2}},
        headers={**headers, "X-Organization-Id": org},
    )
    provider_id = provider.json()["data"]["id"]
    return headers, org, project, provider_id


async def _create_model(client, headers, org, project, provider_id, **cfg_overrides):
    resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": "Test Model",
            "model_identifier": "local-test",
            "provider_id": provider_id,
            "configuration": {"retry_policy": {"max_retries": 0}, **cfg_overrides},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _add_member(client, headers, org, email, role):
    await register(client, email)
    resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": email, "role": role},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_atp1_007_create_model(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id)
    assert model_id


@pytest.mark.asyncio
async def test_atp1_008_model_cross_org_provider_rejected(client):
    # Owner A creates provider; owner B tries to create a model in their project using A's provider.
    await register(client, OWNER)
    headers_a = await headers_for(client, OWNER)
    org_a = await org_id(client, headers_a)
    await create_project(client, headers_a, org_a, name="A", slug="proj-a")
    prov_a = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "A Local"},
        headers={**headers_a, "X-Organization-Id": org_a},
    )
    provider_a = prov_a.json()["data"]["id"]

    await register(client, "modelother@example.com")
    headers_b = await headers_for(client, "modelother@example.com")
    org_b = await org_id(client, headers_b)
    project_b = await create_project(client, headers_b, org_b, name="B", slug="proj-b")
    resp = await client.post(
        f"/api/v1/projects/{project_b}/models",
        json={"name": "M", "model_identifier": "m", "provider_id": provider_a},
        headers={**headers_b, "X-Organization-Id": org_b},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_atp1_009_test_model_connection(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id)
    resp = await client.post(
        f"/api/v1/models/{model_id}/test", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "CONNECTED"
    assert data["latency_ms"] is not None


@pytest.mark.asyncio
async def test_atp1_010_invoke_model_normalized(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id)
    resp = await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "What is the capital of India?"}]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["provider"] == "LOCAL"
    assert data["content"]
    assert data["usage"]["total_tokens"] > 0
    assert data["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_atp1_011_model_timeout(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(
        client, headers, org, project, provider_id, failure_mode="timeout"
    )
    resp = await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 504
    assert resp.json()["error"]["code"] == "TIMEOUT_ERROR"


@pytest.mark.asyncio
async def test_atp1_012_provider_rate_limit_simulated(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(
        client, headers, org, project, provider_id, failure_mode="rate_limit"
    )
    resp = await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_ERROR"


@pytest.mark.asyncio
async def test_atp1_013_authentication_failure(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id, failure_mode="auth")
    resp = await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    # No secret leakage in the error.
    assert "api_key" not in resp.text


@pytest.mark.asyncio
async def test_atp1_014_viewer_invoke_denied(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id)
    await _add_member(client, headers, org, VIEWER, "VIEWER")
    viewer_headers = await headers_for(client, VIEWER)
    resp = await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_atp1_015_engineer_invoke_allowed(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id)
    await _add_member(client, headers, org, ENGINEER, "ENGINEER")
    engineer_headers = await headers_for(client, ENGINEER)
    resp = await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={**engineer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["usage"]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_atp1_029_model_metrics_recorded(client):
    headers, org, project, provider_id = await _owner_ctx(client)
    model_id = await _create_model(client, headers, org, project, provider_id)
    await client.post(
        f"/api/v1/models/{model_id}/invoke",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={**headers, "X-Organization-Id": org},
    )
    metrics = await client.get("/metrics")
    assert "airex_model_requests_total" in metrics.text
    assert "airex_model_request_duration_seconds" in metrics.text
    assert "airex_model_input_tokens_total" in metrics.text
    assert "airex_model_output_tokens_total" in metrics.text
