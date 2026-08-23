"""Phase 2 dataset security tests (spec §41–§43, §56)."""

from __future__ import annotations

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

OWNER = "ds-sec-owner@example.com"
OTHER = "ds-sec-other@example.com"
VIEWER = "ds-sec-viewer@example.com"
JSONL_OK = b'{"input":"q","expected_output":"a"}\n'


async def _ctx(client):
    await register(client, OWNER)
    headers = await headers_for(client, OWNER)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name="Sec Proj", slug="sec-proj")
    return headers, org, project


async def _create_dataset(client, headers, org, project):
    resp = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Sec Dataset"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _upload(
    client, headers, org, dataset_id, content=JSONL_OK, filename="data.jsonl", fmt=None
):
    data = {"format": fmt} if fmt else None
    return await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        files={"file": (filename, content, "application/octet-stream")},
        data=data,
        headers={**headers, "X-Organization-Id": org},
    )


@pytest.mark.asyncio
async def test_sql_injection_in_dataset_name_is_safe(client):
    headers, org, project = await _ctx(client)
    payload = {"name": "x'); DROP TABLE datasets; --", "description": "inject"}
    resp = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json=payload,
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["name"] == payload["name"]
    # Datasets table still usable.
    listed = await client.get(
        f"/api/v1/projects/{project}/datasets", headers={**headers, "X-Organization-Id": org}
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] >= 1


@pytest.mark.asyncio
async def test_sql_injection_in_search_is_safe(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"])).json()["data"]
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/test-cases?search=' OR 1=1 --",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    # The injection must not return all rows (only 0 matches).
    assert resp.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_path_traversal_filename_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client, headers, org, data["id"], filename="..\\..\\secret.jsonl", fmt="jsonl"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATASET_SCHEMA"


@pytest.mark.asyncio
async def test_cross_tenant_dataset_and_version_isolated(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"])).json()["data"]
    await register(client, OTHER)
    other_headers = await headers_for(client, OTHER)
    other_org = await org_id(client, other_headers)
    for url in (
        f"/api/v1/datasets/{data['id']}",
        f"/api/v1/dataset-versions/{version['id']}",
        f"/api/v1/dataset-versions/{version['id']}/export",
        f"/api/v1/dataset-versions/{version['id']}/test-cases",
    ):
        resp = await client.get(url, headers={**other_headers, "X-Organization-Id": other_org})
        assert resp.status_code in (403, 404), url


@pytest.mark.asyncio
async def test_cross_org_project_creation_denied(client):
    """A dataset cannot be created under a project belonging to another org."""
    headers, org, project = await _ctx(client)
    await register(client, OTHER)
    other_headers = await headers_for(client, OTHER)
    other_org = await org_id(client, other_headers)
    resp = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Nope"},
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_viewer_can_read_but_not_mutate(client):
    headers, org, project = await _ctx(client)
    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)

    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"])).json()["data"]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]

    # Read is allowed.
    assert (
        await client.get(
            f"/api/v1/datasets/{data['id']}", headers={**viewer_headers, "X-Organization-Id": org}
        )
    ).status_code == 200
    # Mutations are forbidden.
    create = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Nope"},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert create.status_code == 403
    upload = await _upload(client, viewer_headers, org, data["id"])
    assert upload.status_code == 403
    approve = await client.post(
        f"/api/v1/test-cases/{case_id}/approve",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert approve.status_code == 403


@pytest.mark.asyncio
async def test_oversized_upload_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(client, headers, org, data["id"], content=b"x" * (2 * 1024 * 1024))
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "DATASET_TOO_LARGE"


@pytest.mark.asyncio
async def test_invalid_format_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(client, headers, org, data["id"], JSONL_OK, fmt="pdf")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATASET_FORMAT"


@pytest.mark.asyncio
async def test_malformed_file_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(client, headers, org, data["id"], b"{nope", fmt="json")
    assert resp.status_code == 400
