"""Phase 6 experiment & quality gate API integration tests."""

from __future__ import annotations

import json
import uuid
import pytest

from app.evaluations.experiment_runner import ExperimentRunner, recover_stale_experiments
from app.repositories.experiment import ExperimentRepository
from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)

EMAIL = "p6@example.com"
VIEWER_EMAIL = "p6-viewer@example.com"
OTHER_EMAIL = "p6-other@example.com"

BASE_IDENT = "baseline-model"
CAND_IDENT = "candidate-model"


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="P6 Proj", slug=f"p6-{email.split('@')[0]}"
    )
    return headers, org, project


async def _create_provider(client, headers, org):
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local P6"},
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
        json={"name": "P6 DS"},
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
async def test_atp6_create_experiment_success(client):
    # Test cases where candidate expected outputs are matches
    records = [("What is 2+2?", f"[local:{BASE_IDENT}] What is 2+2?")] * 5
    headers, org, project, model_base, model_cand, version = await _setup(client, records)

    resp = await client.post(
        f"/api/v1/projects/{project}/experiments",
        json={
            "project_id": project,
            "name": "GPT-4 Baseline vs GPT-5 Candidate",
            "experiment_type": "MODEL_COMPARISON",
            "dataset_version_id": version,
            "baseline": {
                "model_id": model_base,
            },
            "candidate": {
                "model_id": model_cand,
            },
            "quality_gates": [
                {
                    "metric_name": "accuracy",
                    "gate_type": "CANDIDATE_VALUE",
                    "operator": "GTE",
                    "threshold": 0.80,
                    "is_required": True,
                }
            ],
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "DRAFT"
    assert data["fingerprint"] is not None


@pytest.mark.asyncio
async def test_atp6_run_experiment_lifecycle(client, session_factory):
    # Setup test cases.
    # Expected output matches the candidate model output: [local:candidate-model] ...
    # This means baseline will get 0% accuracy (since it returns [local:baseline-model] ...),
    # while candidate will get 100% accuracy (since it matches candidate model output).
    # This represents an accuracy IMPROVEMENT (0.0 -> 1.0).
    records = [("What is 2+2?", f"[local:{CAND_IDENT}] What is 2+2?")] * 6
    headers, org, project, model_base, model_cand, version = await _setup(client, records)

    resp_exp = await client.post(
        f"/api/v1/projects/{project}/experiments",
        json={
            "project_id": project,
            "name": "GPT-4 Baseline vs GPT-5 Candidate Run",
            "experiment_type": "MODEL_COMPARISON",
            "dataset_version_id": version,
            "baseline": {
                "model_id": model_base,
            },
            "candidate": {
                "model_id": model_cand,
            },
            "quality_gates": [
                {
                    "metric_name": "accuracy",
                    "gate_type": "CANDIDATE_VALUE",
                    "operator": "GTE",
                    "threshold": 0.80,
                    "is_required": True,
                }
            ],
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_exp.status_code == 201, resp_exp.text
    exp_id = resp_exp.json()["data"]["id"]

    # Start run
    resp_run = await client.post(
        f"/api/v1/experiments/{exp_id}/run",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_run.status_code == 200, resp_run.text
    run_id = resp_run.json()["data"]["id"]

    # Trigger ExperimentRunner execution in-process
    runner = ExperimentRunner(session_factory)
    result = await runner.run(uuid.UUID(run_id))
    assert result["status"] == "COMPLETED"

    # Get results/comparisons
    resp_comp = await client.get(
        f"/api/v1/experiments/{run_id}/results",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_comp.status_code == 200, resp_comp.text
    comps = resp_comp.json()["data"]
    
    accuracy_comp = next((c for c in comps if c["metric_name"] == "accuracy"), None)
    assert accuracy_comp is not None
    assert accuracy_comp["baseline_value"] == 0.0
    assert accuracy_comp["candidate_value"] == 1.0
    assert accuracy_comp["classification"] == "IMPROVED"

    # Get quality gate results
    resp_gates = await client.get(
        f"/api/v1/experiments/{run_id}/quality-gates",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_gates.status_code == 200, resp_gates.text
    gate_results = resp_gates.json()["data"]
    assert len(gate_results) == 1
    assert gate_results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp6_run_experiment_cancellation(client):
    records = [("What is 2+2?", f"[local:{CAND_IDENT}] What is 2+2?")] * 5
    headers, org, project, model_base, model_cand, version = await _setup(client, records)

    resp_exp = await client.post(
        f"/api/v1/projects/{project}/experiments",
        json={
            "project_id": project,
            "name": "Cancel Test",
            "experiment_type": "MODEL_COMPARISON",
            "dataset_version_id": version,
            "baseline": {"model_id": model_base},
            "candidate": {"model_id": model_cand},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    exp_id = resp_exp.json()["data"]["id"]

    resp_run = await client.post(
        f"/api/v1/experiments/{exp_id}/run",
        headers={**headers, "X-Organization-Id": org},
    )
    run_id = resp_run.json()["data"]["id"]

    # Cancel
    resp_cancel = await client.post(
        f"/api/v1/experiments/{run_id}/cancel",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_cancel.status_code == 200, resp_cancel.text
    assert resp_cancel.json()["data"]["status"] == "CANCELLED"
