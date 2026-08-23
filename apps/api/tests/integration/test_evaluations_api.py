"""Evaluation engine API acceptance tests (AT-P3-001..040, Phase 3 §61, §64–§65).

Uses the deterministic LOCAL provider end-to-end: API → service → DB → runner →
Model Gateway → Local adapter → evaluators → results → metrics. No paid calls.
"""

from __future__ import annotations

import uuid

import pytest

from app.evaluations.runner import EvaluationRunner, recover_stale_runs
from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "eval@example.com"
ENGINEER_EMAIL = "eval-engineer@example.com"
OTHER = "eval-other@example.com"
VIEWER = "eval-viewer@example.com"
MODEL_IDENT = "local-eval"

DEFAULT_CFG = {
    "evaluators": [{"type": "exact_match", "enabled": True}],
    "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
}


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="Eval Proj", slug=f"eval-proj-{email.split('@')[0]}"
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
        json={"provider_type": "LOCAL", "name": "Local Eval"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id, config=None):
    resp = await client.post(
        f"/api/v1/projects/{project}/models",
        json={
            "name": MODEL_IDENT,
            "model_identifier": MODEL_IDENT,
            "provider_id": provider_id,
            "configuration": config or {},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_dataset_version(client, headers, org, project, records_jsonl: str) -> str:
    ds = await client.post(
        f"/api/v1/projects/{project}/datasets",
        json={"name": "Eval DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    payload = records_jsonl.encode("utf-8") if isinstance(records_jsonl, str) else records_jsonl
    up = await client.post(
        f"/api/v1/datasets/{ds.json()['data']['id']}/versions",
        files={"file": ("data.jsonl", payload, "application/octet-stream")},
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert up.status_code == 201, up.text
    return up.json()["data"]["id"]


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


async def _execute(session_factory, run_id: str) -> None:
    await EvaluationRunner(session_factory).run(run_id)


async def _setup(client, records_jsonl, model_config=None, email: str = EMAIL):
    headers, org, project = await _ctx(client, email=email)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    model = await _create_model(client, headers, org, project, provider, config=model_config)
    version = await _create_dataset_version(client, headers, org, project, records_jsonl)
    return headers, org, project, env, model, version


def _expected(records):
    """Build a JSONL payload; json.dumps ensures regex/metacharacter escaping."""
    import json

    return "".join(
        json.dumps({"input": r[0], "expected_output": r[1]}, ensure_ascii=False) + "\n"
        for r in records
    ).encode()


# The local provider returns: "[local:local-eval] <input>".
EXPECTED_ACTUAL = f"[local:{MODEL_IDENT}] What is 2+2?"


# ------------------------------------------------------------------ create


@pytest.mark.asyncio
async def test_atp3_001_create_evaluation_queued(client):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    assert run["status"] == "QUEUED"
    assert run["dataset_version_id"] == version
    assert run["model_snapshot"]["model_identifier"] == MODEL_IDENT
    assert run["evaluator_versions"] == {"exact_match": "1.0.0"}


@pytest.mark.asyncio
async def test_atp3_002_invalid_dataset_version(client):
    import uuid as _uuid

    headers, org, project, env, model, _ = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": str(_uuid.uuid4()),
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_atp3_003_model_from_different_project(client):
    headers, org, project, env, _, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    other_project = await create_project(client, headers, org, name="Other", slug="other-proj")
    provider = await _create_provider(client, headers, org)
    model = await _create_model(client, headers, org, other_project, provider)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_atp3_004_dataset_from_different_project(client):
    headers, org, project, env, model, _ = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    other_project = await create_project(client, headers, org, name="Other2", slug="other2")
    version = await _create_dataset_version(
        client, headers, org, other_project, _expected([("a", "b")])
    )
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_atp3_005_viewer_cannot_create(client):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
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


@pytest.mark.asyncio
async def test_atp3_006_engineer_can_create(client):
    await register(client, ENGINEER_EMAIL)
    headers, org, project = await _ctx(client)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": ENGINEER_EMAIL, "role": "ENGINEER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    engineer_headers = await headers_for(client, ENGINEER_EMAIL)
    # The owner provisions the environment/provider/model/dataset (engineers lack
    # manage_environments/manage_providers/manage_models) and the ENGINEER then
    # creates the evaluation (Phase 3 §53: ENGINEER create/run/view/cancel).
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    model = await _create_model(client, headers, org, project, provider)
    version = await _create_dataset_version(
        client, headers, org, project, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": DEFAULT_CFG,
        },
        headers={**engineer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201


# ------------------------------------------------------------- full run


@pytest.mark.asyncio
async def test_atp3_007_run_lifecycle_and_008_all_processed(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client,
        _expected(
            [
                ("What is 2+2?", EXPECTED_ACTUAL),
                ("Capital?", f"[local:{MODEL_IDENT}] Capital?"),
            ]
        ),
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["total_tests"] == 2
    assert got["completed_tests"] == got["total_tests"]  # AT-P3-008


@pytest.mark.asyncio
async def test_atp3_009_exact_match_pass(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "PASS"
    assert results[0]["score"][0]["score"] == 1.0
    assert results[0]["score"][0]["passed"] is True


@pytest.mark.asyncio
async def test_atp3_010_exact_match_fail(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", "5")])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "FAIL"
    assert results[0]["failure_type"] == "ASSERTION_FAILED"
    assert results[0]["score"][0]["score"] == 0.0


@pytest.mark.asyncio
async def test_atp3_011_case_insensitive_match_pass(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", f"[LOCAL:{MODEL_IDENT.upper()}] what is 2+2?")])
    )
    cfg = {
        "evaluators": [{"type": "case_insensitive_exact_match", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp3_012_contains_pass(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", "What is 2+2?")])
    )
    cfg = {
        "evaluators": [{"type": "contains", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp3_013_regex_pass(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", r"^\[local:" + MODEL_IDENT + r"\]")])
    )
    cfg = {
        "evaluators": [{"type": "regex", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp3_014_invalid_regex_errors_without_crash(client, session_factory):
    # Test case 1 has an invalid regex expected pattern → ERROR; test case 2 passes.
    records = _expected([("bad", "(["), ("good", rf"^\[local:{MODEL_IDENT}\]")])
    headers, org, project, env, model, version = await _setup(client, records)
    cfg = {
        "evaluators": [{"type": "regex", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"  # run did not crash
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert got["error_tests"] == 1
    assert any(r["status"] == "ERROR" and r["failure_type"] == "EVALUATOR_ERROR" for r in results)


@pytest.mark.asyncio
async def test_atp3_015_json_match_evaluator(client, session_factory):
    # The LOCAL provider output ("[local:local-eval] ...") is never valid JSON, so
    # json_match reports ASSERTION_FAILED instead of crashing the run.
    headers, org, project, env, model, version = await _setup(
        client,
        _expected([('{"status":"success","count":10}', '{"status":"success","count":10}')]),
    )
    cfg = {
        "evaluators": [{"type": "json_match", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "FAIL"
    assert results[0]["failure_type"] == "ASSERTION_FAILED"
    assert results[0]["score"][0]["evaluator"] == "json_match"


@pytest.mark.asyncio
async def test_atp3_016_numeric_match_with_tolerance(client, session_factory):
    # Numeric expected output parses; the LOCAL output is not numeric -> FAIL.
    headers, org, project, env, model, version = await _setup(client, _expected([("100", "100")]))
    cfg = {
        "evaluators": [{"type": "numeric_match", "enabled": True, "params": {"tolerance": 0.01}}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "FAIL"
    assert results[0]["failure_type"] == "ASSERTION_FAILED"
    assert results[0]["score"][0]["evaluator"] == "numeric_match"


@pytest.mark.asyncio
async def test_atp3_017_numeric_match_invalid_expected_errors(client, session_factory):
    # A non-numeric expected value raises EvaluatorError -> ERROR, not a crash.
    headers, org, project, env, model, version = await _setup(client, _expected([("abc", "abc")]))
    cfg = {
        "evaluators": [{"type": "numeric_match", "enabled": True}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert results[0]["status"] == "ERROR"
    assert results[0]["failure_type"] == "EVALUATOR_ERROR"


@pytest.mark.asyncio
async def test_atp3_018_length_evaluator(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", "ignored")])
    )
    cfg = {
        "evaluators": [{"type": "length", "enabled": True, "params": {"min_length": 5}}],
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    # actual "[local:local-eval] What is 2+2?" length > 5 → PASS
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp3_019_error_continues_run(client, session_factory):
    # Model configured to always timeout → every test case is ERROR, but the run
    # continues and completes (stop_on_error=false).
    headers, org, project, env, model, version = await _setup(
        client,
        _expected([("a", "b"), ("c", "d")]),
        model_config={"failure_mode": "timeout"},
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["error_tests"] == got["total_tests"]
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert all(r["failure_type"] == "TIMEOUT" for r in results)


@pytest.mark.asyncio
async def test_atp3_020_stop_on_error(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client,
        _expected([("a", "b"), ("c", "d"), ("e", "f")]),
        model_config={"failure_mode": "timeout"},
    )
    cfg = {
        "evaluators": [{"type": "exact_match", "enabled": True}],
        "execution": {"max_concurrency": 1, "timeout_seconds": 5, "stop_on_error": True},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["completed_tests"] < got["total_tests"]  # scheduling stopped after error


@pytest.mark.asyncio
async def test_atp3_021_and_022_metrics_and_tokens(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client,
        _expected(
            [
                ("What is 2+2?", EXPECTED_ACTUAL),
                ("Capital?", f"[local:{MODEL_IDENT}] Capital?"),
                ("Bad?", "5"),
            ]
        ),
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    metrics = got["metrics"]
    assert metrics["total_tests"] == 3
    assert metrics["passed"] == 2
    assert metrics["failed"] == 1
    assert metrics["pass_rate"] == pytest.approx(2 / 3, abs=0.001)
    assert metrics["fail_rate"] == pytest.approx(1 / 3, abs=0.001)
    assert metrics["average_latency_ms"] == 0
    assert metrics["total_tokens"] > 0
    assert "evaluators" in metrics


@pytest.mark.asyncio
async def test_atp3_023_one_result_per_test_case(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("a", "b"), ("c", "d")])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results?page_size=50",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()
    assert results["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_atp3_024_duplicate_execution_no_duplicate_results(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("a", "b"), ("c", "d")])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    await _execute(session_factory, run["id"])  # duplicate job
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results?page_size=50",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()
    assert results["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_atp3_025_cancel_queued(client):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    resp = await client.post(
        f"/api/v1/evaluations/{run['id']}/cancel",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_atp3_026_completed_cannot_cancel(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    resp = await client.post(
        f"/api/v1/evaluations/{run['id']}/cancel",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_atp3_027_results_immutable(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    resp = await client.patch(
        f"/api/v1/evaluations/{run['id']}/results/{results[0]['id']}",
        json={"status": "PASS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_atp3_028_dataset_version_fixed(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    # Create v2 of the dataset; the evaluation must still reference v1.
    version2 = await _create_dataset_version(
        client, headers, org, project, _expected([("changed", "content")])
    )
    assert version2 != version
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["dataset_version_id"] == version


@pytest.mark.asyncio
async def test_atp3_029_model_config_snapshot(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client,
        _expected([("What is 2+2?", EXPECTED_ACTUAL)]),
        model_config={"latency_ms": 0, "temperature": 0.1, "max_tokens": 256},
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    # Change the live model configuration after creation.
    await client.patch(
        f"/api/v1/models/{model}",
        json={"configuration": {"temperature": 0.9, "max_tokens": 9999}},
        headers={**headers, "X-Organization-Id": org},
    )
    snapshot = run["model_snapshot"]
    assert snapshot["temperature"] == 0.1
    assert snapshot["max_tokens"] == 256
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["model_snapshot"]["max_tokens"] == 256


@pytest.mark.asyncio
async def test_atp3_030_evaluator_version_snapshot(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert run["evaluator_versions"]["exact_match"] == "1.0.0"
    assert results[0]["score"][0]["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_atp3_031_and_032_cross_org_access(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    await register(client, OTHER)
    other_headers = await headers_for(client, OTHER)
    other_org = await org_id(client, other_headers)
    for url in (
        f"/api/v1/evaluations/{run['id']}",
        f"/api/v1/evaluations/{run['id']}/results",
    ):
        resp = await client.get(url, headers={**other_headers, "X-Organization-Id": other_org})
        assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_atp3_033_viewer_view_completed(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    resp = await client.get(
        f"/api/v1/evaluations/{run['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_atp3_034_viewer_cannot_cancel(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await register(client, VIEWER)
    await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    viewer_headers = await headers_for(client, VIEWER)
    resp = await client.post(
        f"/api/v1/evaluations/{run['id']}/cancel",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_atp3_035_stale_run_recovery(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    # Force the run into RUNNING with an old heartbeat, then recover.
    from datetime import UTC, datetime, timedelta

    from app.repositories.evaluation import EvaluationRepository

    async with session_factory() as session:
        repo = EvaluationRepository(session)
        ev = await repo.get_by_id(uuid.UUID(run["id"]))
        ev.status = "RUNNING"
        ev.heartbeat_at = datetime.now(UTC) - timedelta(seconds=99999)
        await session.commit()
    recovered = await recover_stale_runs(session_factory)
    assert recovered == 1
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "FAILED"


@pytest.mark.asyncio
async def test_atp3_036_and_037_provider_timeout_and_error(client, session_factory):
    for i, failure_mode in enumerate(("timeout", "auth")):
        headers, org, project, env, model, version = await _setup(
            client,
            _expected([("a", "b")]),
            model_config={"failure_mode": failure_mode},
            email=f"eval-fail{i}@example.com",
        )
        run = await _create_eval(client, headers, org, project, env, model, version)
        await _execute(session_factory, run["id"])
        results = (
            await client.get(
                f"/api/v1/evaluations/{run['id']}/results",
                headers={**headers, "X-Organization-Id": org},
            )
        ).json()["data"]
        assert results[0]["status"] == "ERROR"
        expected_type = "TIMEOUT" if failure_mode == "timeout" else "PROVIDER_ERROR"
        assert results[0]["failure_type"] == expected_type


@pytest.mark.asyncio
async def test_atp3_038_audit_events(client, session_factory):
    from sqlalchemy import select

    from app.models import AuditLog

    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    async with session_factory() as session:
        actions = list(
            (
                await session.execute(
                    select(AuditLog.action).where(AuditLog.resource_id == uuid.UUID(run["id"]))
                )
            )
            .scalars()
            .all()
        )
    assert "EVALUATION_CREATED" in actions
    assert "EVALUATION_STARTED" in actions
    assert "EVALUATION_COMPLETED" in actions


@pytest.mark.asyncio
async def test_atp3_039_prometheus_metrics(client, session_factory):
    from app.core.metrics import (
        evaluation_duration_seconds,
        evaluation_runs_total,
        evaluation_tests_total,
    )

    before_runs = evaluation_runs_total.labels(status="COMPLETED")._value.get()
    before_tests = evaluation_tests_total._value.get()
    headers, org, project, env, model, version = await _setup(
        client, _expected([("a", "b"), ("c", "d")])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    assert evaluation_runs_total.labels(status="COMPLETED")._value.get() > before_runs
    assert evaluation_tests_total._value.get() >= before_tests + 2
    assert evaluation_duration_seconds._sum.get() > 0


@pytest.mark.asyncio
async def test_atp3_040_list_pagination_and_filters(client, session_factory):
    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])
    listed = await client.get(
        f"/api/v1/evaluations?project_id={project}&status=COMPLETED&page=1&page_size=5",
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1
    assert listed.json()["data"][0]["id"] == run["id"]


@pytest.mark.asyncio
async def test_worker_task_full_integration(client, session_factory, monkeypatch):
    """Full path: API → service → DB → worker task → runner → Model Gateway →
    Local provider → evaluator → results → metrics (Phase 3 §48, §65).

    The service enqueues a ``run_evaluation`` job on creation; this test
    simulates the worker dequeue/dispatch by invoking the task handler directly
    (with its session factory pointed at the per-test database).
    """
    from app.workers.tasks import TASK_REGISTRY

    monkeypatch.setattr("app.db.session.get_session_factory", lambda: session_factory)

    headers, org, project, env, model, version = await _setup(
        client, _expected([("What is 2+2?", EXPECTED_ACTUAL)])
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    result = await TASK_REGISTRY["run_evaluation"]("job-1", {"evaluation_run_id": run["id"]})
    assert result["status"] == "COMPLETED"

    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["passed_tests"] == 1
    assert got["completed_tests"] == 1
    assert got["metrics"]["total_tests"] == 1

    results = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}/results",
            headers={**headers, "X-Organization-Id": org},
        )
    ).json()["data"]
    assert len(results) == 1
    assert results[0]["status"] == "PASS"
    assert results[0]["failure_type"] is None
    assert results[0]["score"][0]["evaluator"] == "exact_match"
    assert results[0]["score"][0]["passed"] is True


@pytest.mark.asyncio
async def test_evaluation_list_and_result_filters(client, session_factory):
    headers, org, project, env, model, version = await _setup(
        client,
        _expected([("What is 2+2?", EXPECTED_ACTUAL), ("Bad?", "5")]),
    )
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])

    # List filtered by model and dataset version (repository filter branches).
    listed = await client.get(
        f"/api/v1/evaluations?project_id={project}"
        f"&model_id={model}&dataset_version_id={version}&page=1&page_size=10",
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1

    # Results filtered by status and failure type.
    passed = await client.get(
        f"/api/v1/evaluations/{run['id']}/results?status=PASS&page_size=10",
        headers={**headers, "X-Organization-Id": org},
    )
    assert passed.json()["meta"]["total"] == 1
    failed = await client.get(
        f"/api/v1/evaluations/{run['id']}/results?failure_type=ASSERTION_FAILED&page_size=10",
        headers={**headers, "X-Organization-Id": org},
    )
    assert failed.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_result_repository_idempotency_and_get(client, session_factory):
    from app.repositories.dataset import TestCaseRepository
    from app.repositories.evaluation import (
        EvaluationRepository,
        EvaluationResultRepository,
    )

    headers, org, project, env, model, version = await _setup(client, _expected([("a", "b")]))
    run = await _create_eval(client, headers, org, project, env, model, version)
    await _execute(session_factory, run["id"])

    async with session_factory() as session:
        results_repo = EvaluationResultRepository(session)
        run_obj = await EvaluationRepository(session).get_by_id(uuid.UUID(run["id"]))
        case = (await TestCaseRepository(session).all_for_version(uuid.UUID(version)))[0]

        # Re-inserting the same (run, test_case) is suppressed -> None (§49).
        created = await results_repo.create_result(
            run_id=run_obj.id,
            test_case_id=case.id,
            actual_output="x",
            score=None,
            status="PASS",
            failure_type=None,
            failure_message=None,
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )
        assert created is None

        # Result get_by_id round-trips.
        rows, _ = await results_repo.list_for_run(run_obj.id, page=1, page_size=10)
        result = await results_repo.get_by_id(rows[0].id)
        assert result is not None
        assert result.evaluation_run_id == run_obj.id
