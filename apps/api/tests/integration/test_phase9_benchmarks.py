"""Phase 9 benchmarking & reliability scoring integration tests."""

from __future__ import annotations

import json
import pytest
from uuid import UUID

from app.evaluations.benchmark_runner import BenchmarkRunner
from app.repositories.benchmark import BenchmarkRepository
from app.workers.tasks import TASK_REGISTRY
from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)

EMAIL = "p9@example.com"
BASE_IDENT = "baseline-model"
CAND_IDENT = "candidate-model"


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="P9 Proj", slug=f"p9-{email.split('@')[0]}"
    )
    return headers, org, project


async def _create_provider(client, headers, org):
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local P9"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id, ident):
    resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": ident,
            "model_identifier": ident,
            "provider_id": provider_id,
            "configuration": {},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_dataset_version(client, headers, org, project, records):
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "P9 DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    dataset_id = ds.json()["data"]["id"]
    payload = "".join(json.dumps({"input": r[0], "expected_output": r[1]}) + "\n" for r in records)
    up = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        files={"file": ("data.jsonl", payload.encode(), "application/octet-stream")},
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert up.status_code == 201, up.text
    return up.json()["data"]["id"]


async def _setup(client, records):
    headers, org, project = await _ctx(client)
    provider = await _create_provider(client, headers, org)
    model_base = await _create_model(client, headers, org, project, provider, BASE_IDENT)
    model_cand = await _create_model(client, headers, org, project, provider, CAND_IDENT)
    version = await _create_dataset_version(client, headers, org, project, records)
    return headers, org, project, model_base, model_cand, version


@pytest.mark.asyncio
async def test_create_benchmark_suite_invalid_weights(client, session_factory, monkeypatch):
    monkeypatch.setattr("app.workers.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    records = [("Hello", f"[local:{BASE_IDENT}] Hello")] * 5
    headers, org, project, model_base, model_cand, version = await _setup(client, records)

    resp = await client.post(
        f"/api/v1/projects/{project}/benchmarks",
        json={
            "name": "Invalid Weights Benchmark",
            "description": "Weights mismatch",
            "configuration": {
                "dataset_version_id": str(version),
                "baseline": {"model": BASE_IDENT},
                "candidates": [{"model": CAND_IDENT}],
                "weights": {
                    "accuracy": 0.5,
                    "latency_ms": 0.3
                }
            }
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    suite_id = resp.json()["data"]["id"]

    resp_run = await client.post(
        f"/api/v1/benchmarks/{suite_id}/runs",
        json={},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_run.status_code == 201
    run_id = resp_run.json()["data"]["id"]

    runner = BenchmarkRunner(session_factory)
    res = await runner.run(UUID(run_id))
    assert res["status"] == "FAILED"

    resp_status = await client.get(
        f"/api/v1/benchmarks/runs/{run_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_status.status_code == 200
    run_detail = resp_status.json()["data"]
    assert run_detail["run"]["status"] == "FAILED"
    assert "weights must sum to 1.0" in run_detail["run"]["error_message"].lower()


@pytest.mark.asyncio
async def test_benchmark_run_lifecycle_success(client, session_factory, monkeypatch):
    monkeypatch.setattr("app.workers.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    records = [("Hello", f"[local:{CAND_IDENT}] Hello")] * 5
    headers, org, project, model_base, model_cand, version = await _setup(client, records)

    resp = await client.post(
        f"/api/v1/projects/{project}/benchmarks",
        json={
            "name": "Reliability Benchmark 1",
            "description": "Benchmark testing",
            "configuration": {
                "dataset_version_id": str(version),
                "baseline": {"model": BASE_IDENT},
                "candidates": [{"model": CAND_IDENT}],
                "weights": {
                    "accuracy": 0.4,
                    "latency_ms": 0.2,
                    "estimated_cost": 0.1,
                    "consistency": 0.1,
                    "safety": 0.2
                }
            }
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    suite_id = resp.json()["data"]["id"]

    resp_run = await client.post(
        f"/api/v1/benchmarks/{suite_id}/runs",
        json={},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_run.status_code == 201
    run_id = resp_run.json()["data"]["id"]

    from app.db.session import get_session_factory
    runner = BenchmarkRunner(get_session_factory())
    res = await runner.run(UUID(run_id))
    assert res["status"] == "COMPLETED"

    resp_results = await client.get(
        f"/api/v1/benchmarks/runs/{run_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_results.status_code == 200
    data = resp_results.json()["data"]
    
    assert data["run"]["status"] == "COMPLETED"
    assert data["run"]["reliability_score"] is not None
    assert len(data["results"]) == 1
    assert len(data["evidences"]) > 0
    assert data["recommendation"] is not None


@pytest.mark.asyncio
async def test_benchmark_rbac_restrictions_viewer(client, session_factory, monkeypatch):
    monkeypatch.setattr("app.workers.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    records = [("Hello", f"[local:{CAND_IDENT}] Hello")] * 5
    headers, org, project, model_base, model_cand, version = await _setup(client, records)

    viewer_email = "p9-viewer@example.com"
    await register(client, viewer_email)
    viewer_headers = await headers_for(client, viewer_email)
    
    from app.models.organization import OrganizationMember
    from app.core.permissions import Role
    from app.models.user import User
    
    from datetime import datetime, UTC
    async with session_factory() as session:
        from sqlalchemy import select
        res = await session.execute(select(User).where(User.email == viewer_email))
        viewer_user = res.scalar_one()
        session.add(OrganizationMember(
            organization_id=UUID(org),
            user_id=viewer_user.id,
            role=Role.VIEWER,
            created_at=datetime.now(UTC),
        ))
        await session.commit()

    resp = await client.post(
        f"/api/v1/projects/{project}/benchmarks",
        json={
            "name": "Viewer Benchmark",
            "configuration": {
                "dataset_version_id": str(version),
                "baseline": {"model": BASE_IDENT},
                "candidates": [{"model": CAND_IDENT}],
                "weights": {"accuracy": 1.0}
            }
        },
        headers={**viewer_headers, "X-Organization-Id": str(org)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_benchmark_tenant_isolation(client, session_factory, monkeypatch):
    monkeypatch.setattr("app.workers.worker.get_session_factory", lambda: session_factory)
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    records = [("Hello", f"[local:{CAND_IDENT}] Hello")] * 5
    headers, org, project, model_base, model_cand, version = await _setup(client, records)
    
    resp = await client.post(
        f"/api/v1/projects/{project}/benchmarks",
        json={
            "name": "Org A Benchmark",
            "configuration": {
                "dataset_version_id": str(version),
                "baseline": {"model": BASE_IDENT},
                "candidates": [{"model": CAND_IDENT}],
                "weights": {"accuracy": 1.0}
            }
        },
        headers={**headers, "X-Organization-Id": str(org)},
    )
    assert resp.status_code == 201
    suite_id = resp.json()["data"]["id"]

    other_email = "p9-other@example.com"
    await register(client, other_email)
    other_headers = await headers_for(client, other_email)
    
    org_b = await org_id(client, other_headers)

    resp_get = await client.get(
        f"/api/v1/benchmarks/{suite_id}",
        headers={**other_headers, "X-Organization-Id": str(org_b)},
    )
    assert resp_get.status_code == 404
