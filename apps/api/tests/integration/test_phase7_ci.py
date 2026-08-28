"""Integration tests for Phase 7 CI/CD and Service Token endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from uuid import uuid4

from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "ci_integration@example.com"


async def _ctx(client: AsyncClient):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name="CI Proj", slug="ci-proj")
    return headers, org, project


@pytest.mark.asyncio
async def test_service_token_lifecycle(client: AsyncClient) -> None:
    headers, org, project_id = await _ctx(client)

    # 1. Create a service token
    payload = {
        "name": "GitHub Actions",
        "scopes": ["experiments:run", "experiments:read"],
        "expires_in_days": 30,
    }
    resp = await client.post(
        f"/api/v1/projects/{project_id}/service-tokens",
        json=payload,
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    envelope = resp.json()
    assert "data" in envelope
    data = envelope["data"]
    assert data["name"] == "GitHub Actions"
    assert "raw_token" in data
    assert data["token_prefix"].startswith("airex_ci_")
    
    raw_token = data["raw_token"]
    token_id = data["id"]

    # 2. List service tokens
    resp_list = await client.get(
        f"/api/v1/projects/{project_id}/service-tokens",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_list.status_code == 200, resp_list.text
    list_data = resp_list.json()["data"]
    assert len(list_data) >= 1
    assert any(t["id"] == token_id for t in list_data)

    # 3. Rotate service token
    resp_rotate = await client.post(
        f"/api/v1/service-tokens/{token_id}/rotate",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_rotate.status_code == 200, resp_rotate.text
    rotate_data = resp_rotate.json()["data"]
    assert rotate_data["id"] != token_id
    assert "raw_token" in rotate_data
    
    new_raw_token = rotate_data["raw_token"]
    new_token_id = rotate_data["id"]

    # 4. Revoke service token
    resp_revoke = await client.delete(
        f"/api/v1/service-tokens/{new_token_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_revoke.status_code == 200, resp_revoke.text
    assert resp_revoke.json()["data"]["status"] == "revoked"


@pytest.mark.asyncio
async def test_service_token_authentication_and_scopes(client: AsyncClient) -> None:
    headers, org, project_id = await _ctx(client)

    # Create service token with limited scope "experiments:read"
    payload = {
        "name": "Read Only CI",
        "scopes": ["experiments:read"],
    }
    resp = await client.post(
        f"/api/v1/projects/{project_id}/service-tokens",
        json=payload,
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    raw_token = data["raw_token"]

    ci_headers = {
        "Authorization": f"Bearer {raw_token}",
        "X-Organization-Id": org,
    }

    # 1. Fetching experiments should succeed (experiments:read is permitted)
    resp_exps = await client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers=ci_headers,
    )
    assert resp_exps.status_code == 200, resp_exps.text

    # 2. Creating an experiment should fail (lack of experiments:write)
    exp_payload = {
        "project_id": str(project_id),
        "name": "CI Attempt",
        "description": "Should fail",
        "dataset_id": str(uuid4()),
        "dataset_version_id": str(uuid4()),
        "baseline": {"model_id": str(uuid4()), "prompt_content": "A", "configuration": {}},
        "candidate": {"model_id": str(uuid4()), "prompt_content": "B", "configuration": {}},
        "gates": [],
    }
    resp_create = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json=exp_payload,
        headers=ci_headers,
    )
    assert resp_create.status_code == 403  # Forbidden
