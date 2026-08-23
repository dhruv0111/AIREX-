"""Environment API tests (AT-P1-016..018)."""

from __future__ import annotations

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "env@example.com"


async def _ctx(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name="Env Proj", slug="env-proj")
    return headers, org, project


@pytest.mark.asyncio
async def test_atp1_016_create_development_environment(client):
    headers, org, project = await _ctx(client)
    resp = await client.post(
        f"/api/v1/projects/{project}/environments",
        json={"name": "Dev", "environment_type": "DEVELOPMENT"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["environment_type"] == "DEVELOPMENT"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_atp1_017_duplicate_environment_type_conflict(client):
    headers, org, project = await _ctx(client)
    for _ in range(2):
        resp = await client.post(
            f"/api/v1/projects/{project}/environments",
            json={"name": "Dev", "environment_type": "DEVELOPMENT"},
            headers={**headers, "X-Organization-Id": org},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_atp1_018_create_staging_and_production(client):
    headers, org, project = await _ctx(client)
    for env_type in ("DEVELOPMENT", "STAGING", "PRODUCTION"):
        resp = await client.post(
            f"/api/v1/projects/{project}/environments",
            json={"name": env_type.lower(), "environment_type": env_type},
            headers={**headers, "X-Organization-Id": org},
        )
        assert resp.status_code == 201, resp.text
    # All three types now exist.
    resp = await client.get(
        f"/api/v1/projects/{project}/environments", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


@pytest.mark.asyncio
async def test_environment_update_and_delete(client):
    headers, org, project = await _ctx(client)
    created = await client.post(
        f"/api/v1/projects/{project}/environments",
        json={"name": "Dev", "environment_type": "DEVELOPMENT"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert created.status_code == 201, created.text
    env_id = created.json()["data"]["id"]
    updated = await client.patch(
        f"/api/v1/environments/{env_id}",
        json={"name": "Dev Renamed", "status": "INACTIVE"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Dev Renamed"
    deleted = await client.delete(
        f"/api/v1/environments/{env_id}", headers={**headers, "X-Organization-Id": org}
    )
    assert deleted.status_code == 204, deleted.text
