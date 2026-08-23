"""Dataset management API acceptance tests (AT-P2-001..036, Phase 2 §55)."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.datasets import checksum
from app.models import AuditLog
from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "datasets@example.com"
OTHER = "datasets-other@example.com"
CSV_OK = (
    "input,expected_output,category\n"
    '"What is 2+2?","4","math"\n'
    '"Capital of India?","New Delhi","general"\n'
)
JSONL_OK = (
    '{"input":"What is 2+2?","expected_output":"4","category":"math"}\n'
    '{"input":"Capital of India?","expected_output":"New Delhi","category":"general"}\n'
)


async def _ctx(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name="Dataset Proj", slug="dataset-proj")
    return headers, org, project


async def _create_dataset(client, headers, org, project, name="Support Dataset"):
    resp = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": name, "description": "desc", "metadata": {"owner": "qa"}},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _upload(
    client, headers, org, dataset_id, content: bytes, filename="data.jsonl", fmt=None
):
    data = {"format": fmt} if fmt else None
    return await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        files={"file": (filename, content, "application/octet-stream")},
        data=data,
        headers={**headers, "X-Organization-Id": org},
    )


async def _audit_actions(session_factory, resource_id=None, action=None):
    async with session_factory() as session:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at.asc())
        if resource_id is not None:
            stmt = stmt.where(AuditLog.resource_id == UUID(resource_id))
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        return list((await session.execute(stmt)).scalars().all())


# ------------------------------------------------------------------ datasets


@pytest.mark.asyncio
async def test_atp2_001_create_dataset(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    assert data["status"] == "ACTIVE"
    assert data["version_count"] == 0


@pytest.mark.asyncio
async def test_atp2_002_list_datasets(client):
    headers, org, project = await _ctx(client)
    await _create_dataset(client, headers, org, project, name="A")
    await _create_dataset(client, headers, org, project, name="B")
    resp = await client.get(
        f"/api/v1/projects/{project}/datasets?page=1&page_size=10",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 2
    assert {d["name"] for d in resp.json()["data"]} == {"A", "B"}


@pytest.mark.asyncio
async def test_atp2_003_get_dataset_details(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await client.get(
        f"/api/v1/datasets/{data['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == data["id"]


@pytest.mark.asyncio
async def test_atp2_004_update_dataset_metadata(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await client.patch(
        f"/api/v1/datasets/{data['id']}",
        json={"name": "Renamed", "metadata": {"k": "v"}},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Renamed"
    assert resp.json()["data"]["metadata"] == {"k": "v"}


@pytest.mark.asyncio
async def test_atp2_005_archive_dataset(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await client.delete(
        f"/api/v1/datasets/{data['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 204
    detail = await client.get(
        f"/api/v1/datasets/{data['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert detail.json()["data"]["status"] == "ARCHIVED"


# ------------------------------------------------------------------ versions


@pytest.mark.asyncio
async def test_atp2_006_create_version_from_csv(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client, headers, org, data["id"], CSV_OK.encode("utf-8"), filename="data.csv", fmt="csv"
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["version_number"] == 1
    assert resp.json()["data"]["record_count"] == 2


@pytest.mark.asyncio
async def test_atp2_007_create_second_version(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    for _ in range(2):
        resp = await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))
        assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["version_number"] == 2


@pytest.mark.asyncio
async def test_atp2_008_version_numbering_per_dataset(client):
    headers, org, project = await _ctx(client)
    a = await _create_dataset(client, headers, org, project, name="A")
    b = await _create_dataset(client, headers, org, project, name="B")
    for ds in (a, b):
        resp = await _upload(client, headers, org, ds["id"], JSONL_OK.encode("utf-8"))
        assert resp.json()["data"]["version_number"] == 1


@pytest.mark.asyncio
async def test_atp2_009_duplicate_version_number_conflict(client, session_factory):
    """The (dataset_id, version_number) unique constraint blocks duplicates."""
    from app.repositories.dataset import DatasetVersionRepository

    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    # Create v1 through the API, then attempt a duplicate v1 directly.
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    assert version["version_number"] == 1
    async with session_factory() as session:
        version_repo = DatasetVersionRepository(session)
        with pytest.raises(IntegrityError):
            await version_repo.create(
                dataset_id=UUID(data["id"]),
                version_number=1,
                storage_reference="k2",
                record_count=0,
                checksum="y" * 64,
                fmt="jsonl",
                status="COMPLETED",
                created_by=None,
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_atp2_010_malformed_csv_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client,
        headers,
        org,
        data["id"],
        b"not,a,valid,csv,without,input\n1,2\n",
        filename="x.csv",
        fmt="csv",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in ("INVALID_DATASET_SCHEMA", "INVALID_DATASET_FORMAT")


@pytest.mark.asyncio
async def test_atp2_011_malformed_json_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(client, headers, org, data["id"], b"{not json", fmt="json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATASET_SCHEMA"


@pytest.mark.asyncio
async def test_atp2_012_malformed_jsonl_reports_line(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    body = b'{"input":"q1","expected_output":"a1"}\n{bad\n{"input":"q3","expected_output":"a3"}\n'
    resp = await _upload(client, headers, org, data["id"], body, fmt="jsonl")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATASET_SCHEMA"
    assert "line 2" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_atp2_013_missing_input_validation(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client,
        headers,
        org,
        data["id"],
        b'{"expected_output":"a"}\n',
        fmt="jsonl",
    )
    assert resp.status_code == 400
    details = resp.json()["error"]["details"]["validation"]
    assert any(e["code"] == "EMPTY_VALUE" for e in details["errors"])


@pytest.mark.asyncio
async def test_atp2_014_missing_expected_output_validation(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(client, headers, org, data["id"], b'{"input":"q"}\n', fmt="jsonl")
    assert resp.status_code == 400
    details = resp.json()["error"]["details"]["validation"]
    assert any(e["field"] == "expected_output" for e in details["errors"])


@pytest.mark.asyncio
async def test_atp2_015_empty_input_validation(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client, headers, org, data["id"], b'{"input":"  ","expected_output":"a"}\n', fmt="jsonl"
    )
    assert resp.status_code == 400
    assert any(
        e["code"] == "EMPTY_VALUE" for e in resp.json()["error"]["details"]["validation"]["errors"]
    )


@pytest.mark.asyncio
async def test_atp2_016_invalid_utf8_encoding(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client,
        headers,
        org,
        data["id"],
        b'{"input":"\xff\xfe","expected_output":"a"}\n',
        fmt="jsonl",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATASET_ENCODING"


@pytest.mark.asyncio
async def test_atp2_017_file_exceeds_max_size(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    oversized = b"x" * (2 * 1024 * 1024)  # 2 MB > 1 MB test limit
    resp = await _upload(client, headers, org, data["id"], oversized, fmt="jsonl")
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "DATASET_TOO_LARGE"


@pytest.mark.asyncio
async def test_atp2_018_record_count_exceeds_limit(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    body = "".join(f'{{"input":"q{i}","expected_output":"a{i}"}}\n' for i in range(101)).encode(
        "utf-8"
    )
    resp = await _upload(client, headers, org, data["id"], body, fmt="jsonl")
    assert resp.status_code == 400
    assert any(
        e["code"] == "TOO_MANY_RECORDS"
        for e in resp.json()["error"]["details"]["validation"]["errors"]
    )


@pytest.mark.asyncio
async def test_atp2_019_checksum_generated(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))
    assert resp.status_code == 201
    checksum_value = resp.json()["data"]["checksum"]
    assert len(checksum_value) == 64
    int(checksum_value, 16)


@pytest.mark.asyncio
async def test_atp2_020_same_canonical_content_same_checksum(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    v1 = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()["data"]
    v2 = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()["data"]
    assert v1["checksum"] == v2["checksum"]


@pytest.mark.asyncio
async def test_atp2_021_version_immutable(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    resp = await client.patch(
        f"/api/v1/dataset-versions/{version['id']}",
        json={"record_count": 999},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DATASET_VERSION_IMMUTABLE"


@pytest.mark.asyncio
async def test_atp2_022_test_cases_belong_to_correct_version(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    v1 = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()["data"]
    v2_body = b'{"input":"only","expected_output":"one"}\n'
    v2 = (await _upload(client, headers, org, data["id"], v2_body)).json()["data"]

    r1 = await client.get(
        f"/api/v1/dataset-versions/{v1['id']}/test-cases",
        headers={**headers, "X-Organization-Id": org},
    )
    r2 = await client.get(
        f"/api/v1/dataset-versions/{v2['id']}/test-cases",
        headers={**headers, "X-Organization-Id": org},
    )
    assert r1.status_code == 200 and r1.json()["meta"]["total"] == 2
    assert all(c["dataset_version_id"] == v1["id"] for c in r1.json()["data"])
    assert r2.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_atp2_023_test_case_pagination(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    body = "".join(f'{{"input":"q{i}","expected_output":"a{i}"}}\n' for i in range(5)).encode()
    version = (await _upload(client, headers, org, data["id"], body)).json()["data"]
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/test-cases?page=1&page_size=2",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 5
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_atp2_024_test_case_search(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    body = (
        b'{"input":"What is the capital of India?","expected_output":"New Delhi"}\n'
        b'{"input":"What is 2+2?","expected_output":"4"}\n'
    )
    version = (await _upload(client, headers, org, data["id"], body)).json()["data"]
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/test-cases?search=capital",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.json()["meta"]["total"] == 1
    assert "capital" in resp.json()["data"][0]["input"].lower()


@pytest.mark.asyncio
async def test_atp2_025_test_case_status_filter(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]
    await client.post(
        f"/api/v1/test-cases/{case_id}/approve", headers={**headers, "X-Organization-Id": org}
    )
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/test-cases?status=APPROVED",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.json()["meta"]["total"] == 1
    assert resp.json()["data"][0]["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_atp2_026_approve_test_case_with_audit(client, session_factory):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]
    resp = await client.post(
        f"/api/v1/test-cases/{case_id}/approve", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "APPROVED"
    assert await _audit_actions(session_factory, resource_id=case_id, action="TEST_CASE_APPROVED")


@pytest.mark.asyncio
async def test_atp2_027_reject_test_case_with_audit(client, session_factory):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]
    resp = await client.post(
        f"/api/v1/test-cases/{case_id}/reject", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "REJECTED"
    assert await _audit_actions(session_factory, resource_id=case_id, action="TEST_CASE_REJECTED")


@pytest.mark.asyncio
async def test_atp2_028_export_version(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=jsonl",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"{")
    assert b"What is 2+2?" in resp.content


@pytest.mark.asyncio
async def test_atp2_029_exported_checksum_equals_original(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    for fmt in ("jsonl", "json"):
        resp = await client.get(
            f"/api/v1/dataset-versions/{version['id']}/export?format={fmt}",
            headers={**headers, "X-Organization-Id": org},
        )
        assert resp.status_code == 200
        from app.datasets import parse_dataset

        records = parse_dataset(resp.content.decode("utf-8"), fmt)
        assert checksum(records) == version["checksum"]


# ------------------------------------------------------------------ security


@pytest.mark.asyncio
async def test_atp2_030_cross_org_dataset_access(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    await register(client, OTHER)
    other_headers = await headers_for(client, OTHER)
    other_org = await org_id(client, other_headers)
    resp = await client.get(
        f"/api/v1/datasets/{data['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_atp2_031_cross_org_version_access(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    await register(client, OTHER)
    other_headers = await headers_for(client, OTHER)
    other_org = await org_id(client, other_headers)
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_atp2_032_cross_org_test_case_access(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]
    await register(client, OTHER)
    other_headers = await headers_for(client, OTHER)
    other_org = await org_id(client, other_headers)
    resp = await client.get(
        f"/api/v1/test-cases/{case_id}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_atp2_033_path_traversal_filename_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client,
        headers,
        org,
        data["id"],
        JSONL_OK.encode("utf-8"),
        filename="../../secret.jsonl",
        fmt="jsonl",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATASET_SCHEMA"


@pytest.mark.asyncio
async def test_atp2_034_failed_import_leaves_no_partial_version(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await _upload(
        client, headers, org, data["id"], b'{"input":"","expected_output":"a"}\n', fmt="jsonl"
    )
    assert resp.status_code == 400
    detail = await client.get(
        f"/api/v1/datasets/{data['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert detail.json()["data"]["version_count"] == 0
    versions = await client.get(
        f"/api/v1/datasets/{data['id']}/versions", headers={**headers, "X-Organization-Id": org}
    )
    assert versions.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_atp2_035_archive_prevents_new_versions(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    await client.delete(
        f"/api/v1/datasets/{data['id']}", headers={**headers, "X-Organization-Id": org}
    )
    resp = await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DATASET_ARCHIVED"


@pytest.mark.asyncio
async def test_atp2_036_version_history_intact(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    v1 = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()["data"]
    v2_body = b'{"input":"new","expected_output":"version"}\n'
    v2 = (await _upload(client, headers, org, data["id"], v2_body)).json()["data"]
    # v1 is unchanged after v2 is created
    r1 = await client.get(
        f"/api/v1/dataset-versions/{v1['id']}", headers={**headers, "X-Organization-Id": org}
    )
    r1_data = r1.json()["data"]
    assert r1_data["checksum"] == v1["checksum"]
    assert r1_data["record_count"] == v1["record_count"]
    assert v2["version_number"] == 2


# ------------------------------------------------------------------ concurrency


@pytest.mark.asyncio
async def test_concurrent_version_creation_distinct_numbers(client):
    """Two simultaneous imports must never produce the same version number."""
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)

    async def _upload_once():
        return await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))

    r1, r2 = await asyncio.gather(_upload_once(), _upload_once())
    assert r1.status_code == 201 and r2.status_code == 201
    numbers = {r.json()["data"]["version_number"] for r in (r1, r2)}
    assert numbers == {1, 2}


@pytest.mark.asyncio
async def test_viewer_cannot_create_dataset(client):
    """VIEWER lacks manage_datasets: creation/import/approve are forbidden."""

    viewer_email = "viewer-ds@example.com"
    await register(client, viewer_email)
    headers, org, project = await _ctx(client)
    # Owner adds the viewer to the org.
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": viewer_email, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, viewer_email)
    resp = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Nope"},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "AUTHZ_FORBIDDEN"


# ------------------------------------------ targeted coverage: get/list/filter


@pytest.mark.asyncio
async def test_dataset_version_get_and_list(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    got = await client.get(
        f"/api/v1/dataset-versions/{version['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert got.status_code == 200
    assert got.json()["data"]["checksum"] == version["checksum"]
    listed = await client.get(
        f"/api/v1/datasets/{data['id']}/versions?page=1&page_size=5",
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_missing_dataset_version_returns_404(client):
    import uuid as _uuid

    headers, org, project = await _ctx(client)
    resp = await client.get(
        f"/api/v1/dataset-versions/{_uuid.uuid4()}", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DATASET_VERSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_single_test_case(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]
    resp = await client.get(
        f"/api/v1/test-cases/{case_id}", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == case_id


@pytest.mark.asyncio
async def test_test_case_category_and_difficulty_filters(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    body = (
        b'{"input":"q1","expected_output":"a1","category":"math","difficulty":"easy"}\n'
        b'{"input":"q2","expected_output":"a2","category":"general","difficulty":"hard"}\n'
    )
    version = (await _upload(client, headers, org, data["id"], body)).json()["data"]
    by_category = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/test-cases?category=math",
        headers={**headers, "X-Organization-Id": org},
    )
    assert by_category.json()["meta"]["total"] == 1
    assert by_category.json()["data"][0]["category"] == "math"
    by_difficulty = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/test-cases?difficulty=hard",
        headers={**headers, "X-Organization-Id": org},
    )
    assert by_difficulty.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_export_csv_format(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    resp = await client.get(
        f"/api/v1/dataset-versions/{version['id']}/export?format=csv",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert b"input,expected_output" in resp.content


@pytest.mark.asyncio
async def test_patch_test_case_immutable_rejected(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    version = (await _upload(client, headers, org, data["id"], JSONL_OK.encode("utf-8"))).json()[
        "data"
    ]
    case_id = (
        await client.get(
            f"/api/v1/dataset-versions/{version['id']}/test-cases",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"][0]["id"]
    resp = await client.patch(
        f"/api/v1/test-cases/{case_id}",
        json={"input": "changed"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DATASET_VERSION_IMMUTABLE"


@pytest.mark.asyncio
async def test_update_dataset_description_and_status(client):
    headers, org, project = await _ctx(client)
    data = await _create_dataset(client, headers, org, project)
    resp = await client.patch(
        f"/api/v1/datasets/{data['id']}",
        json={"description": "new desc", "status": "ACTIVE"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "new desc"
