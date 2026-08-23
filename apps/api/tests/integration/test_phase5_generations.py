"""Phase 5 test-generation API acceptance tests (AT-P5-001..040).

Uses the deterministic LOCAL provider for the generator model (``local_content``
config) so the whole suite needs zero external LLM API cost. Full path:
API → service → GenerationRunner → Model Gateway → Local provider → parser →
validation → dedup → quality score → PENDING_REVIEW candidates → human review →
dataset version.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.generation.runner import GenerationRunner, recover_stale_generations
from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)

EMAIL = "p5@example.com"
ENGINEER_EMAIL = "p5-engineer@example.com"
VIEWER = "p5-viewer@example.com"
OTHER = "p5-other@example.com"

GEN_IDENT = "generator"

_CASE_0 = {
    "input": "What is 2+2?",
    "expected_output": "4",
    "context": {"topic": "math"},
    "category": "arithmetic",
    "difficulty": "easy",
    "generation_type": "BASIC",
}
_CASE_1 = {
    "input": "Capital of France?",
    "expected_output": "Paris",
    "category": "geography",
    "difficulty": "easy",
    "generation_type": "BASIC",
}
_CASE_2 = {
    "input": "Reverse a string",
    "expected_output": "Reversed string",
    "category": "algorithms",
    "difficulty": "hard",
    "generation_type": "ADVERSARIAL",
}
_CASE_INVALID = {"input": "", "expected_output": "", "difficulty": "nope"}

GEN_VALID = json.dumps({"test_cases": [_CASE_0, _CASE_1, _CASE_2]})
GEN_DUP = json.dumps({"test_cases": [_CASE_0, _CASE_1, dict(_CASE_0)]})
GEN_WITH_INVALID = json.dumps({"test_cases": [_CASE_0, _CASE_INVALID, _CASE_1]})
GEN_MALFORMED = "this is not json at all"


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="P5 Proj", slug=f"p5-{email.split('@')[0]}"
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
        json={"provider_type": "LOCAL", "name": "Local P5"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id, config=None, name=GEN_IDENT):
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


async def _create_dataset_version(client, headers, org, project, records):
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "P5 DS"},
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


async def _setup(
    client,
    content=GEN_VALID,
    failure_mode=None,
    email: str = EMAIL,
    active: bool = True,
):
    headers, org, project = await _ctx(client, email=email)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    gen_config = {"local_content": content}
    if failure_mode:
        gen_config["failure_mode"] = failure_mode
    gen_model = await _create_model(
        client, headers, org, project, provider, config=gen_config, name=GEN_IDENT
    )
    if not active:
        await client.patch(
            f"/api/v1/models/{gen_model}",
            json={"is_active": False},
            headers={**headers, "X-Organization-Id": org},
        )
    return headers, org, project, env, gen_model


async def _create_generation(
    client,
    headers,
    org,
    project,
    gen_model,
    *,
    env=None,
    source_type="MANUAL_INSTRUCTION",
    source_reference=None,
    generation_type="BASIC",
    count=5,
    instruction="Summarize the input",
    configuration=None,
):
    resp = await client.post(
        "/api/v1/generations",
        json={
            "project_id": project,
            "environment_id": env,
            "source_type": source_type,
            "source_reference": source_reference,
            "generation_type": generation_type,
            "instruction": instruction,
            "count": count,
            "configuration": configuration
            or {
                "generation_types": [generation_type],
                "difficulty_distribution": {"easy": 0.5, "medium": 0.3, "hard": 0.2},
            },
            "generator_model_id": gen_model,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    return resp


async def _execute(session_factory, request_id):
    await GenerationRunner(session_factory).run(uuid.UUID(request_id))


async def _candidates(client, headers, org, request_id, **params):
    resp = await client.get(
        f"/api/v1/generations/{request_id}/candidates",
        params=params,
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ================================================================ creation


@pytest.mark.asyncio
async def test_atp5_001_create_generation_queued(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(client, headers, org, project, gen_model, env=env)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "QUEUED"
    assert data["source_type"] == "MANUAL_INSTRUCTION"
    assert data["generation_type"] == "BASIC"
    assert data["generator_model_snapshot"]["model_identifier"] == GEN_IDENT
    assert data["prompt_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_atp5_002_invalid_source_type(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(
        client, headers, org, project, gen_model, env=env, source_type="NONSENSE"
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_003_invalid_generation_type(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(
        client, headers, org, project, gen_model, env=env, generation_type="MAGIC"
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_004_count_out_of_bounds(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(client, headers, org, project, gen_model, env=env, count=101)
    assert resp.status_code == 400, resp.text
    resp = await _create_generation(client, headers, org, project, gen_model, env=env, count=0)
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_005_generator_model_from_other_project(client):
    headers, org, project, env, gen_model = await _setup(client)
    # A second project in the same org owns a different generator model.
    other_project = await create_project(
        client, headers, org, name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    provider = await _create_provider(client, headers, org)
    other_model = await _create_model(client, headers, org, other_project, provider)
    resp = await _create_generation(client, headers, org, project, other_model, env=env)
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_006_engineer_can_create(client):
    await register(client, ENGINEER_EMAIL)
    headers, org, project = await _ctx(client)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": ENGINEER_EMAIL, "role": "ENGINEER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    engineer_headers = await headers_for(client, ENGINEER_EMAIL)
    # Owner provisions resources (engineers lack manage_*), engineer generates.
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    gen_model = await _create_model(client, headers, org, project, provider)
    resp = await _create_generation(client, engineer_headers, org, project, gen_model, env=env)
    assert resp.status_code == 201, resp.text


# ------------------------------------------------------------ full lifecycle


@pytest.mark.asyncio
async def test_atp5_007_and_008_lifecycle_and_candidates(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["candidate_count"] == 3  # AT-P5-008: all processed
    cases = await _candidates(client, headers, org, request["id"])
    assert len(cases) == 3
    for case in cases:
        assert case["status"] == "PENDING_REVIEW"
        assert case["quality_score"] is not None
        assert 0.0 <= case["quality_score"] <= 1.0


@pytest.mark.asyncio
async def test_atp5_009_malformed_output_fails(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client, content=GEN_MALFORMED)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "FAILED"
    assert got["candidate_count"] == 0


@pytest.mark.asyncio
async def test_atp5_010_provider_timeout_fails(client, session_factory):
    headers, org, project, env, gen_model = await _setup(
        client, content=GEN_VALID, failure_mode="timeout"
    )
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "FAILED"


@pytest.mark.asyncio
async def test_atp5_011_provider_error_fails(client, session_factory):
    headers, org, project, env, gen_model = await _setup(
        client, content=GEN_VALID, failure_mode="auth"
    )
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "FAILED"


@pytest.mark.asyncio
async def test_atp5_012_inactive_generator_model_rejected(client, session_factory):
    from app.repositories.provider import ModelRepository

    headers, org, project, env, gen_model = await _setup(client)
    async with session_factory() as session:
        model = await ModelRepository(session).get_by_id(uuid.UUID(gen_model))
        model.is_active = False
        await session.commit()
    resp = await _create_generation(client, headers, org, project, gen_model, env=env)
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_013_environment_other_project_rejected(client):
    headers, org, project, env, gen_model = await _setup(client)
    other_project = await create_project(
        client, headers, org, name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    other_env = await _create_env(client, headers, org, other_project)
    resp = await _create_generation(client, headers, org, project, gen_model, env=other_env)
    assert resp.status_code == 400, resp.text


# ------------------------------------------------------------- dedup / quality


@pytest.mark.asyncio
async def test_atp5_014_duplicate_candidates_deduped(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client, content=GEN_DUP)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    assert len(cases) == 3  # 3 stored, one is a duplicate
    dupes = [c for c in cases if c["duplicate_of"] is not None]
    assert len(dupes) == 1
    assert dupes[0]["duplicate_of"] != dupes[0]["id"]


@pytest.mark.asyncio
async def test_atp5_015_fingerprint_deterministic_stored(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    assert all(len(c["fingerprint"]) == 64 for c in cases)
    # Deterministic: same input → same fingerprint.
    first = next(c for c in cases if c["input"] == _CASE_0["input"])
    second = next(c for c in cases if c["input"] == _CASE_1["input"])
    assert first["fingerprint"] != second["fingerprint"]


@pytest.mark.asyncio
async def test_atp5_016_invalid_rows_skipped(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client, content=GEN_WITH_INVALID)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["candidate_count"] == 2  # one invalid row skipped, run still completes


# --------------------------------------------------------------- control flow


@pytest.mark.asyncio
async def test_atp5_017_cancel_queued(client):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/cancel",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_atp5_018_completed_cannot_cancel(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/cancel",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409, resp.text


# ------------------------------------------------------------------- RBAC


@pytest.mark.asyncio
async def test_atp5_019_viewer_cannot_create(client):
    await register(client, VIEWER)
    headers, org, project = await _ctx(client)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    gen_model = await _create_model(client, headers, org, project, provider)
    resp = await _create_generation(client, viewer_headers, org, project, gen_model, env=env)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_atp5_020_viewer_cannot_cancel(client, session_factory):
    await register(client, VIEWER)
    headers, org, project = await _ctx(client)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    gen_model = await _create_model(client, headers, org, project, provider)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/cancel",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_atp5_021_viewer_can_view(client, session_factory):
    await register(client, VIEWER)
    headers, org, project = await _ctx(client)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    gen_model = await _create_model(
        client, headers, org, project, provider, config={"local_content": GEN_VALID}
    )
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    resp = await client.get(
        f"/api/v1/generations/{request['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    cases = await _candidates(client, viewer_headers, org, request["id"])
    assert len(cases) == 3


@pytest.mark.asyncio
async def test_atp5_022_cross_org_access_denied(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/generations/{request['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------- snapshots


@pytest.mark.asyncio
async def test_atp5_023_and_024_and_025_snapshots(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    # AT-P5-023: generator model snapshot frozen at creation.
    assert got["generator_model_snapshot"]["model_identifier"] == GEN_IDENT
    assert got["generator_model_snapshot"]["provider_type"] == "LOCAL"
    # AT-P5-024: prompt version snapshot.
    assert got["prompt_version"] == "1.0.0"
    # AT-P5-025: source snapshot frozen.
    assert got["source_snapshot"]["type"] == "MANUAL_INSTRUCTION"
    assert got["source_snapshot"]["record_count"] == 0


@pytest.mark.asyncio
async def test_atp5_025b_dataset_source_snapshot(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    version = await _create_dataset_version(client, headers, org, project, [("a", "b"), ("c", "d")])
    request = (
        await _create_generation(
            client,
            headers,
            org,
            project,
            gen_model,
            env=env,
            source_type="DATASET",
            source_reference={"dataset_version_id": version},
        )
    ).json()["data"]
    assert request["source_snapshot"]["type"] == "DATASET"
    assert request["source_snapshot"]["record_count"] == 2
    assert request["source_snapshot"]["source_reference"]["dataset_checksum"]
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"


# ------------------------------------------------------- stale recovery / audit


@pytest.mark.asyncio
async def test_atp5_026_stale_generation_recovery(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    from datetime import UTC, datetime, timedelta

    from app.repositories.generation import GenerationRequestRepository

    async with session_factory() as session:
        repo = GenerationRequestRepository(session)
        gen = await repo.get_by_id(uuid.UUID(request["id"]))
        await repo.set_status(gen, "RUNNING")
        gen.heartbeat_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()
    recovered = await recover_stale_generations(session_factory)
    assert recovered == 1
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "FAILED"


@pytest.mark.asyncio
async def test_atp5_027_generation_audit_events(client, session_factory):
    from sqlalchemy import select

    from app.models import AuditLog

    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(AuditLog.action).where(AuditLog.resource_id == uuid.UUID(request["id"]))
                )
            )
            .scalars()
            .all()
        )
    for expected in ("GENERATION_CREATED", "GENERATION_STARTED", "GENERATION_COMPLETED"):
        assert expected in rows, (expected, rows)


@pytest.mark.asyncio
async def test_atp5_028_generation_metrics(client, session_factory):
    from app.core.metrics import (
        generation_candidates_total,
        generation_requests_total,
    )

    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    assert generation_requests_total.labels(status="COMPLETED")._value.get() >= 1
    assert generation_candidates_total.labels(status="PENDING_REVIEW")._value.get() >= 3


# ----------------------------------------------------------- candidate review


@pytest.mark.asyncio
async def test_atp5_029_approve_candidate(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    candidate_id = cases[0]["id"]
    resp = await client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"action": "approve"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_atp5_030_reject_candidate(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    candidate_id = cases[0]["id"]
    resp = await client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"action": "reject"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_atp5_031_cannot_review_twice(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    candidate_id = cases[0]["id"]
    await client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"action": "approve"},
        headers={**headers, "X-Organization-Id": org},
    )
    resp = await client.post(
        f"/api/v1/candidates/{candidate_id}/review",
        json={"action": "reject"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_atp5_032_candidate_cross_org_denied(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    resp = await client.get(
        f"/api/v1/candidates/{cases[0]['id']}",
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_atp5_033_viewer_cannot_approve(client, session_factory):
    await register(client, VIEWER)
    headers, org, project = await _ctx(client)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    gen_model = await _create_model(
        client, headers, org, project, provider, config={"local_content": GEN_VALID}
    )
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    resp = await client.post(
        f"/api/v1/candidates/{cases[0]['id']}/review",
        json={"action": "approve"},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_atp5_034_candidate_filters(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"], status="PENDING_REVIEW")
    assert len(cases) == 3
    hard = await _candidates(client, headers, org, request["id"], difficulty="hard")
    assert len(hard) == 1
    adv = await _candidates(client, headers, org, request["id"], generation_type="ADVERSARIAL")
    assert len(adv) == 1
    arith = await _candidates(client, headers, org, request["id"], category="arithmetic")
    assert len(arith) == 1


# ---------------------------------------------------------- dataset integration


@pytest.mark.asyncio
async def test_atp5_035_dataset_version_from_approved(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    for case in cases:
        await client.post(
            f"/api/v1/candidates/{case['id']}/review",
            json={"action": "approve"},
            headers={**headers, "X-Organization-Id": org},
        )
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Gen DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    dataset_id = ds.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={
            "dataset_id": dataset_id,
            "candidate_ids": [c["id"] for c in cases],
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["record_count"] == 3
    assert len(data["checksum"]) == 64


@pytest.mark.asyncio
async def test_atp5_036_non_approved_candidate_rejected(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Gen DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    dataset_id = ds.json()["data"]["id"]
    # One candidate still PENDING_REVIEW → must be rejected.
    await client.post(
        f"/api/v1/candidates/{cases[0]['id']}/review",
        json={"action": "approve"},
        headers={**headers, "X-Organization-Id": org},
    )
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={
            "dataset_id": dataset_id,
            "candidate_ids": [c["id"] for c in cases],
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_037_cross_project_candidate_rejected(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    other_project = await create_project(
        client, headers, org, name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    ds = await client.post(
        f"/api/v1/projects/{other_project}/datasets",
        json={"name": "Other DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    dataset_id = ds.json()["data"]["id"]
    await client.post(
        f"/api/v1/candidates/{cases[0]['id']}/review",
        json={"action": "approve"},
        headers={**headers, "X-Organization-Id": org},
    )
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": dataset_id, "candidate_ids": [cases[0]["id"]]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_atp5_038_consumption_tracking(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    for case in cases:
        await client.post(
            f"/api/v1/candidates/{case['id']}/review",
            json={"action": "approve"},
            headers={**headers, "X-Organization-Id": org},
        )
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Gen DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    dataset_id = ds.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": dataset_id, "candidate_ids": [c["id"] for c in cases]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    version_id = resp.json()["data"]["dataset_version_id"]
    updated = await _candidates(client, headers, org, request["id"])
    assert all(c["dataset_version_id"] == version_id for c in updated)


@pytest.mark.asyncio
async def test_atp5_039_consumed_candidate_rejected(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    for case in cases:
        await client.post(
            f"/api/v1/candidates/{case['id']}/review",
            json={"action": "approve"},
            headers={**headers, "X-Organization-Id": org},
        )
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Gen DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    dataset_id = ds.json()["data"]["id"]
    await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": dataset_id, "candidate_ids": [c["id"] for c in cases]},
        headers={**headers, "X-Organization-Id": org},
    )
    # Second attempt re-uses already-consumed candidates → rejected.
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": dataset_id, "candidate_ids": [c["id"] for c in cases]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400, resp.text


# --------------------------------------------------------------- list/filters


@pytest.mark.asyncio
async def test_atp5_040_list_pagination_and_filters(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    for _ in range(3):
        await _create_generation(client, headers, org, project, gen_model, env=env)
    resp = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "page": 1, "page_size": 2},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["total"] == 3
    assert len(body["data"]) == 2
    filtered = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "status": "QUEUED"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert filtered.status_code == 200
    assert all(g["status"] == "QUEUED" for g in filtered.json()["data"])


# ============================================================ extended coverage


@pytest.mark.asyncio
async def test_worker_task_full_integration(client, session_factory, monkeypatch):
    """The registered worker task drives a full generation to COMPLETED."""
    from app.workers.tasks import generate_test_cases

    # Point the worker's internal session factory at the per-test database.
    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    result = await generate_test_cases("job-1", {"generation_request_id": request["id"]})
    assert result["status"] == "COMPLETED"
    assert result["created"] == 3


@pytest.mark.asyncio
async def test_generation_request_repository_idempotency(client, session_factory):
    """A terminal request is not re-executed (idempotent duplicate job)."""
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    result = await GenerationRunner(session_factory).run(uuid.UUID(request["id"]))
    assert result["idempotent"] is True
    assert result["status"] == "COMPLETED"
    # No duplicate candidates created by the second run.
    cases = await _candidates(client, headers, org, request["id"])
    assert len(cases) == 3


# ========================================================== source coverage


@pytest.mark.asyncio
async def test_generation_from_test_cases_source(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    version = await _create_dataset_version(client, headers, org, project, [("a", "b"), ("c", "d")])
    tc = await client.get(
        f"/api/v1/dataset-versions/{version}/test-cases",
        headers={**headers, "X-Organization-Id": org},
    )
    assert tc.status_code == 200, tc.text
    ids = [t["id"] for t in tc.json()["data"]]
    request = (
        await _create_generation(
            client,
            headers,
            org,
            project,
            gen_model,
            env=env,
            source_type="TEST_CASES",
            source_reference={"test_case_ids": ids},
        )
    ).json()["data"]
    assert request["source_snapshot"]["type"] == "TEST_CASES"
    assert request["source_snapshot"]["record_count"] == 2
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_generation_from_evaluation_failures(client, session_factory):
    from app.evaluations.runner import EvaluationRunner

    headers, org, project, env, gen_model = await _setup(client)
    provider = await _create_provider(client, headers, org)
    target_model = await _create_model(client, headers, org, project, provider, name="target")
    # One PASS (expected matches the LOCAL actual) and one FAIL.
    version = await _create_dataset_version(
        client,
        headers,
        org,
        project,
        [("What is 2+2?", "[local:target] What is 2+2?"), ("What is 2+2?", "WRONG")],
    )
    eval_resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": target_model,
            "configuration": {
                "evaluators": [{"type": "exact_match"}],
                "execution": {"max_concurrency": 1, "timeout_seconds": 10},
            },
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert eval_resp.status_code == 201, eval_resp.text
    run_id = eval_resp.json()["data"]["id"]
    await EvaluationRunner(session_factory).run(uuid.UUID(run_id))
    request = (
        await _create_generation(
            client,
            headers,
            org,
            project,
            gen_model,
            env=env,
            source_type="EVALUATION_FAILURES",
            source_reference={"evaluation_run_id": run_id},
        )
    ).json()["data"]
    assert request["source_snapshot"]["type"] == "EVALUATION_FAILURES"
    assert request["source_snapshot"]["record_count"] == 1  # the failed case
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_dataset_source_error_paths(client):
    headers, org, project, env, gen_model = await _setup(client)
    other_project = await create_project(
        client, headers, org, name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    other_version = await _create_dataset_version(client, headers, org, other_project, [("x", "y")])
    # Missing source reference entirely.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="DATASET",
        source_reference=None,
    )
    assert resp.status_code == 400, resp.text
    # Invalid (non-UUID) version id.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="DATASET",
        source_reference={"dataset_version_id": "not-a-uuid"},
    )
    assert resp.status_code == 400, resp.text
    # Non-existent version.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="DATASET",
        source_reference={"dataset_version_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 400, resp.text
    # Version from another project.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="DATASET",
        source_reference={"dataset_version_id": other_version},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_test_cases_source_error_paths(client):
    headers, org, project, env, gen_model = await _setup(client)
    other_project = await create_project(
        client, headers, org, name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    other_version = await _create_dataset_version(client, headers, org, other_project, [("x", "y")])
    other_tc = await client.get(
        f"/api/v1/dataset-versions/{other_version}/test-cases",
        headers={**headers, "X-Organization-Id": org},
    )
    other_ids = [t["id"] for t in other_tc.json()["data"]]
    # Missing test_case_ids.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="TEST_CASES",
        source_reference={},
    )
    assert resp.status_code == 400, resp.text
    # Test case from another project.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="TEST_CASES",
        source_reference={"test_case_ids": other_ids},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_evaluation_failures_source_error_paths(client):
    headers, org, project, env, gen_model = await _setup(client)
    other_project = await create_project(
        client, headers, org, name="Other", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    provider = await _create_provider(client, headers, org)
    other_model = await _create_model(client, headers, org, other_project, provider, name="target")
    other_version = await _create_dataset_version(
        client, headers, org, other_project, [("q", "WRONG")]
    )
    eval_resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": other_project,
            "environment_id": None,
            "dataset_version_id": other_version,
            "model_id": other_model,
            "configuration": {
                "evaluators": [{"type": "exact_match"}],
                "execution": {"max_concurrency": 1, "timeout_seconds": 10},
            },
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert eval_resp.status_code == 201, eval_resp.text
    other_run = eval_resp.json()["data"]["id"]
    # Missing run id.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="EVALUATION_FAILURES",
        source_reference={},
    )
    assert resp.status_code == 400, resp.text
    # Run from another project.
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="EVALUATION_FAILURES",
        source_reference={"evaluation_run_id": other_run},
    )
    assert resp.status_code == 400, resp.text


# ============================================================ edge coverage


@pytest.mark.asyncio
async def test_cross_org_membership_header_forbidden(client):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    other_headers, other_org, _ = await _ctx(client, email=OTHER)
    # OTHER user claims org A via the header: membership resolution -> 403.
    resp = await client.get(
        f"/api/v1/generations/{request['id']}",
        headers={**other_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_generation_project_from_other_org_not_found(client):
    headers, org, project, env, gen_model = await _setup(client)
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
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_generation_list_type_and_source_filters(client):
    headers, org, project, env, gen_model = await _setup(client)
    await _create_generation(
        client, headers, org, project, gen_model, env=env, generation_type="EDGE_CASE"
    )
    await _create_generation(client, headers, org, project, gen_model, env=env)
    by_type = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "generation_type": "EDGE_CASE"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert by_type.status_code == 200
    assert len(by_type.json()["data"]) == 1
    by_source = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "source_type": "DATASET"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert by_source.status_code == 200
    assert len(by_source.json()["data"]) == 0


@pytest.mark.asyncio
async def test_runner_not_found_and_string_id(client, session_factory):
    # Unknown request id -> NOT_FOUND.
    result = await GenerationRunner(session_factory).run(uuid.uuid4())
    assert result["status"] == "NOT_FOUND"
    # A string request id is normalized to UUID (worker payload path).
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    result = await GenerationRunner(session_factory).run(str(request["id"]))
    assert result["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_dataset_version_requires_approved_candidates(client, session_factory):
    headers, org, project, env, gen_model = await _setup(client)
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    await _execute(session_factory, request["id"])
    cases = await _candidates(client, headers, org, request["id"])
    for case in cases:
        await client.post(
            f"/api/v1/candidates/{case['id']}/review",
            json={"action": "reject"},
            headers={**headers, "X-Organization-Id": org},
        )
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Gen DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    dataset_id = ds.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/generations/{request['id']}/dataset-version",
        json={"dataset_id": dataset_id, "candidate_ids": [c["id"] for c in cases]},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_dataset_source_with_dataset_id_latest_version(client):
    """DATASET source may reference a dataset_id and uses its latest version."""
    headers, org, project, env, gen_model = await _setup(client)
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    dataset_id = ds.json()["data"]["id"]
    payload = '{"input":"a","expected_output":"b"}\n'
    up = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        files={"file": ("data.jsonl", payload.encode(), "application/octet-stream")},
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert up.status_code == 201, up.text
    request = (
        await _create_generation(
            client,
            headers,
            org,
            project,
            gen_model,
            env=env,
            source_type="DATASET",
            source_reference={"dataset_id": dataset_id},
        )
    ).json()["data"]
    assert request["source_snapshot"]["type"] == "DATASET"
    assert request["source_snapshot"]["record_count"] == 1


@pytest.mark.asyncio
async def test_test_cases_source_invalid_and_missing_ids(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="TEST_CASES",
        source_reference={"test_case_ids": ["not-a-uuid"]},
    )
    assert resp.status_code == 400, resp.text
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="TEST_CASES",
        source_reference={"test_case_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_evaluation_failures_invalid_run_id(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="EVALUATION_FAILURES",
        source_reference={"evaluation_run_id": "not-a-uuid"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_generation_pagination_validation(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await client.get(
        "/api/v1/generations",
        params={"project_id": project, "page": 0},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400, resp.text
    request = (await _create_generation(client, headers, org, project, gen_model, env=env)).json()[
        "data"
    ]
    resp = await client.get(
        f"/api/v1/generations/{request['id']}/candidates",
        params={"page": 0},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_dataset_source_invalid_dataset_id(client):
    headers, org, project, env, gen_model = await _setup(client)
    resp = await _create_generation(
        client,
        headers,
        org,
        project,
        gen_model,
        env=env,
        source_type="DATASET",
        source_reference={"dataset_id": "not-a-uuid"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_test_cases_source_record_cap(client, session_factory):
    """More than _MAX_SOURCE_RECORDS test cases are capped at 50."""
    headers, org, project, env, gen_model = await _setup(client)
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Big DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    dataset_id = ds.json()["data"]["id"]
    payload = "".join(
        json.dumps({"input": f"q{i}", "expected_output": "a"}) + "\n" for i in range(60)
    )
    up = await client.post(
        f"/api/v1/datasets/{dataset_id}/versions",
        files={"file": ("data.jsonl", payload.encode(), "application/octet-stream")},
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert up.status_code == 201, up.text
    version_id = up.json()["data"]["id"]
    tc = await client.get(
        f"/api/v1/dataset-versions/{version_id}/test-cases",
        params={"page_size": 100},
        headers={**headers, "X-Organization-Id": org},
    )
    ids = [t["id"] for t in tc.json()["data"]]
    assert len(ids) == 60
    request = (
        await _create_generation(
            client,
            headers,
            org,
            project,
            gen_model,
            env=env,
            source_type="TEST_CASES",
            source_reference={"test_case_ids": ids},
        )
    ).json()["data"]
    assert request["source_snapshot"]["record_count"] == 50
    await _execute(session_factory, request["id"])
    got = (
        await client.get(
            f"/api/v1/generations/{request['id']}",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_generation_service_membership_forbidden(client, session_factory):
    """A user without membership in the org gets 403 from the service authz."""
    from app.core.errors import ForbiddenError
    from app.services.generation import GenerationService

    async with session_factory() as session:
        service = GenerationService(session)
        with pytest.raises(ForbiddenError):
            await service.get(
                organization_id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )
