"""Phase 4 evaluation engine API acceptance tests (AT-P4-001..040, spec §51–§55).

Uses the deterministic LOCAL provider for both the target model and the judge
model (``local_content`` config) so the whole suite needs zero external LLM API
cost. Full path: API → service → runner → Model Gateway → Local provider →
judge → validation → results → metrics.
"""

from __future__ import annotations

import uuid

import pytest

from app.evaluations.runner import EvaluationRunner
from tests.integration._helpers import create_project, headers_for, org_id, register

EMAIL = "p4@example.com"
ENGINEER_EMAIL = "p4-engineer@example.com"
OTHER = "p4-other@example.com"
OTHER2 = "p4-other2@example.com"
VIEWER = "p4-viewer@example.com"

TARGET_IDENT = "target"
JUDGE_IDENT = "judge"

RUBRIC_CRITERIA = [
    {"name": "correctness", "description": "Factually correct", "weight": 0.5},
    {"name": "relevance", "description": "Directly addresses the question", "weight": 0.3},
    {"name": "clarity", "description": "Understandable", "weight": 0.2},
]

JUDGE_VALID = (
    '{"criteria": {"correctness": 0.9, "relevance": 0.8, "clarity": 1.0}, '
    '"overall_score": 0.89, "passed": true, "confidence": 0.91, '
    '"reasoning": "Factually correct and directly relevant."}'
)
JUDGE_MALFORMED = "this is not json at all"
JUDGE_OUT_OF_RANGE = (
    '{"criteria": {"correctness": 1.5}, "overall_score": 0.5, '
    '"passed": true, "confidence": 0.5, "reasoning": "x"}'
)
JUDGE_UNKNOWN = (
    '{"criteria": {"bogus_criterion": 0.5}, "overall_score": 0.5, '
    '"passed": true, "confidence": 0.5, "reasoning": "x"}'
)
JUDGE_LOW = (
    '{"criteria": {"correctness": 0.2, "relevance": 0.2, "clarity": 0.2}, '
    '"overall_score": 0.2, "passed": false, "confidence": 0.6, "reasoning": "Weak answer."}'
)
JUDGE_HIGH = (
    '{"criteria": {"correctness": 0.95, "relevance": 0.95, "clarity": 0.95}, '
    '"overall_score": 0.95, "passed": true, "confidence": 0.95, '
    '"reasoning": "Excellent and fully correct."}'
)

TARGET_ACTUAL = f"[local:{TARGET_IDENT}] "


async def _ctx(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="P4 Proj", slug=f"p4-{email.split('@')[0]}"
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
        json={"provider_type": "LOCAL", "name": "Local P4"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_model(client, headers, org, project, provider_id, config=None, name=TARGET_IDENT):
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
        json={"name": "P4 DS"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert ds.status_code == 201, ds.text
    import json as _json

    payload = "".join(_json.dumps({"input": r[0], "expected_output": r[1]}) + "\n" for r in records)
    up = await client.post(
        f"/api/v1/datasets/{ds.json()['data']['id']}/versions",
        files={"file": ("data.jsonl", payload.encode(), "application/octet-stream")},
        data={"format": "jsonl"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert up.status_code == 201, up.text
    return up.json()["data"]["id"]


async def _create_rubric(client, headers, org, project, criteria=None, name="Answer Quality"):
    resp = await client.post(
        "/api/v1/rubrics",
        json={
            "project_id": project,
            "name": name,
            "description": "Rubric for P4",
            "criteria": criteria or RUBRIC_CRITERIA,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _setup(
    client,
    records,
    judge_content=JUDGE_VALID,
    judge_failure_mode=None,
    email: str = EMAIL,
):
    headers, org, project = await _ctx(client, email=email)
    env = await _create_env(client, headers, org, project)
    provider = await _create_provider(client, headers, org)
    model = await _create_model(client, headers, org, project, provider, name=TARGET_IDENT)
    judge_config = {"local_content": judge_content}
    if judge_failure_mode:
        judge_config["failure_mode"] = judge_failure_mode
    judge_model = await _create_model(
        client, headers, org, project, provider, config=judge_config, name=JUDGE_IDENT
    )
    version = await _create_dataset_version(client, headers, org, project, records)
    rubric = await _create_rubric(client, headers, org, project)
    return headers, org, project, env, model, version, judge_model, rubric


def _judge_cfg(judge_model_id, rubric_id, **overrides):
    evaluator = {
        "type": "llm_judge",
        "enabled": True,
        "judge_model_id": judge_model_id,
        "rubric_id": rubric_id,
        "threshold": overrides.pop("threshold", 0.75),
        "reference_required": overrides.pop("reference_required", True),
    }
    if "weight" in overrides:
        evaluator["weight"] = overrides.pop("weight")
    evaluators = overrides.pop("evaluators", None) or [evaluator]
    execution = {
        "max_concurrency": overrides.pop("max_concurrency", 4),
        "timeout_seconds": 10,
        "stop_on_error": overrides.pop("stop_on_error", False),
    }
    if "pass_policy" in overrides:
        execution["pass_policy"] = overrides.pop("pass_policy")
    if "exec_threshold" in overrides:
        execution["threshold"] = overrides.pop("exec_threshold")
    return {"evaluators": evaluators, "execution": execution}


async def _create_eval(client, headers, org, project, env, model, version, configuration):
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": project,
            "environment_id": env,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": configuration,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _execute(session_factory, run_id):
    await EvaluationRunner(session_factory).run(uuid.UUID(run_id))


async def _results(client, headers, org, run_id):
    resp = await client.get(
        f"/api/v1/evaluations/{run_id}/results",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ==================================================================== rubrics


@pytest.mark.asyncio
async def test_atp4_001_create_valid_rubric(client):
    headers, org, project = await _ctx(client)
    rubric = await _create_rubric(client, headers, org, project)
    assert rubric["version"] == 1
    assert rubric["status"] == "ACTIVE"
    total = sum(c["weight"] for c in rubric["criteria"])
    assert total == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_atp4_002_invalid_rubric_weights(client):
    headers, org, project = await _ctx(client)
    resp = await client.post(
        "/api/v1/rubrics",
        json={
            "project_id": project,
            "name": "Bad",
            "criteria": [
                {"name": "a", "description": "x", "weight": 0},
                {"name": "b", "description": "y", "weight": 0},
            ],
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_atp4_003_rubric_versioning(client):
    headers, org, project = await _ctx(client)
    v1 = await _create_rubric(client, headers, org, project, name="QA")
    v2 = await _create_rubric(client, headers, org, project, name="QA")
    assert v1["version"] == 1
    assert v2["version"] == 2
    # Only the latest version stays ACTIVE; v1 is archived.
    got = await client.get(
        f"/api/v1/rubrics/{v1['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert got.json()["data"]["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_atp4_004_used_rubric_immutable(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    resp = await client.patch(
        f"/api/v1/rubrics/{rubric['id']}",
        json={"name": "Renamed"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_atp4_018_viewer_cannot_create_rubric(client):
    headers, org, project = await _ctx(client)
    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    resp = await client.post(
        "/api/v1/rubrics",
        json={
            "project_id": project,
            "name": "Viewer Rubric",
            "criteria": RUBRIC_CRITERIA,
        },
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_atp4_019_viewer_can_view_rubric(client):
    headers, org, project = await _ctx(client)
    rubric = await _create_rubric(client, headers, org, project)
    await register(client, VIEWER)
    add = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": VIEWER, "role": "VIEWER"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert add.status_code == 201, add.text
    viewer_headers = await headers_for(client, VIEWER)
    got = await client.get(
        f"/api/v1/rubrics/{rubric['id']}",
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert got.status_code == 200


@pytest.mark.asyncio
async def test_atp4_039_sql_injection_safe(client):
    headers, org, project = await _ctx(client)
    resp = await client.post(
        "/api/v1/rubrics",
        json={
            "project_id": project,
            "name": "x' OR '1'='1",
            "criteria": RUBRIC_CRITERIA,
        },
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    listed = await client.get(
        f"/api/v1/rubrics?project_id={project}&status=ACTIVE' OR '1'='1",
        headers={**headers, "X-Organization-Id": org},
    )
    assert listed.status_code == 200


# ============================================================ judge evaluation


@pytest.mark.asyncio
async def test_atp4_005_create_llm_judge_evaluation(client):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    assert run["status"] == "QUEUED"
    assert run["judge_model_snapshot"] is not None
    assert run["judge_rubric_snapshot"] is not None
    assert run["judge_prompt_version"] == "1.0.0"
    assert run["evaluator_versions"]["llm_judge"] == "1.0.0"


@pytest.mark.asyncio
async def test_atp4_006_and_007_valid_judge_response_passes(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "PASS"
    assert results[0]["judge_score"] == pytest.approx(0.89)
    assert results[0]["judge_confidence"] == pytest.approx(0.91)
    assert results[0]["judge_reasoning"]
    assert results[0]["judge_criteria_scores"]["correctness"] == pytest.approx(0.9)
    assert results[0]["judge_model_snapshot"]["model_identifier"] == JUDGE_IDENT
    assert results[0]["judge_rubric_snapshot"]["version"] == 1


@pytest.mark.asyncio
async def test_atp4_008_malformed_judge_json_errors(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")], judge_content=JUDGE_MALFORMED
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"  # no crash
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "ERROR"
    assert results[0]["failure_type"] == "EVALUATOR_ERROR"


@pytest.mark.asyncio
async def test_atp4_009_score_out_of_range_errors(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")], judge_content=JUDGE_OUT_OF_RANGE
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "ERROR"
    assert results[0]["failure_type"] == "EVALUATOR_ERROR"


@pytest.mark.asyncio
async def test_atp4_010_unknown_criterion_errors(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")], judge_content=JUDGE_UNKNOWN
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "ERROR"
    assert results[0]["failure_type"] == "EVALUATOR_ERROR"


@pytest.mark.asyncio
async def test_atp4_011_weighted_score_exact_math(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"], threshold=0.5, pass_policy="WEIGHTED", weight=1.0)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "PASS"
    assert results[0]["combined_score"] == pytest.approx(0.89)


@pytest.mark.asyncio
async def test_atp4_012_threshold_pass(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"], threshold=0.75)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp4_013_threshold_fail(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")], judge_content=JUDGE_LOW
    )
    cfg = _judge_cfg(judge_model, rubric["id"], threshold=0.75)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "FAIL"
    assert results[0]["judge_score"] == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_atp4_014_reference_based(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"], reference_required=True)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp4_015_reference_free(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"], reference_required=False)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp4_016_judge_model_cross_org(client):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    other_headers, other_org, other_project = await _ctx(client, email=OTHER)
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": other_project,
            "environment_id": None,
            "dataset_version_id": version,
            "model_id": model,
            "configuration": _judge_cfg(judge_model, rubric["id"]),
        },
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_atp4_017_cross_tenant_rubric(client):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    other_headers, other_org, other_project = await _ctx(client, email=OTHER)
    other_provider = await _create_provider(client, other_headers, other_org)
    other_model = await _create_model(
        client, other_headers, other_org, other_project, other_provider, name=TARGET_IDENT
    )
    other_version = await _create_dataset_version(
        client, other_headers, other_org, other_project, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "project_id": other_project,
            "environment_id": None,
            "dataset_version_id": other_version,
            "model_id": other_model,
            "configuration": _judge_cfg(judge_model, rubric["id"]),
        },
        headers={**other_headers, "X-Organization-Id": other_org},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_atp4_020_judge_timeout(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")], judge_failure_mode="timeout"
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "ERROR"
    assert results[0]["failure_type"] == "TIMEOUT"


@pytest.mark.asyncio
async def test_atp4_021_judge_provider_error(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")], judge_failure_mode="auth"
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["status"] == "ERROR"
    assert results[0]["failure_type"] == "PROVIDER_ERROR"


@pytest.mark.asyncio
async def test_atp4_022_judge_retry(monkeypatch):
    """Transient judge failure is retried by the Model Gateway then succeeds."""
    from app.core.config import get_settings
    from app.integrations.gateway import ModelGatewayService
    from app.integrations.provider import ErrorCategory, LocalProviderAdapter, ProviderError
    from app.judge.base import JudgeCriterion, JudgeRubric
    from app.judge.cache import JudgeCache
    from app.judge.llm_judge import ModelGatewayJudge

    calls = {"n": 0}

    class FlakyLocal(LocalProviderAdapter):
        async def invoke(self, request):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ProviderError(ErrorCategory.RATE_LIMIT_ERROR, "transient")
            return await super().invoke(request)

    monkeypatch.setattr(
        "app.integrations.gateway.build_adapter",
        lambda provider_type, cfg, settings=None: FlakyLocal(cfg, settings),
    )

    rubric = JudgeRubric(
        name="R",
        description=None,
        version=1,
        criteria=[
            JudgeCriterion("correctness", "Correct", 0.5),
            JudgeCriterion("relevance", "Relevant", 0.3),
            JudgeCriterion("clarity", "Clear", 0.2),
        ],
    )
    judge = ModelGatewayJudge(
        gateway=ModelGatewayService(get_settings()),
        session=None,
        cache=JudgeCache(),
        organization_id=uuid.uuid4(),
    )
    result = await judge.evaluate(
        input_text="q",
        expected_output=None,
        actual_output="a",
        rubric=rubric,
        context=None,
        judge_snapshot={
            "provider_id": str(uuid.uuid4()),
            "model_identifier": "judge",
            "provider_type": "LOCAL",
            "configuration": {"local_content": JUDGE_VALID},
            "model_version": "1.0.0",
        },
        reference_required=True,
        timeout=10,
    )
    assert calls["n"] == 3  # 2 transient failures + 1 success
    assert result.score == pytest.approx(0.89)


@pytest.mark.asyncio
async def test_atp4_023_judge_cache_hit(client, session_factory):
    from app.core.metrics import llm_judge_cache_hits_total, llm_judge_requests_total

    before_req = llm_judge_requests_total._value.get()
    before_hits = llm_judge_cache_hits_total._value.get()
    # Two identical test cases -> the second judge call is a cache hit. Run
    # sequentially (max_concurrency=1) so the first result is cached first.
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("same", f"{TARGET_ACTUAL}same"), ("same", f"{TARGET_ACTUAL}same")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"], max_concurrency=1)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    after_req = llm_judge_requests_total._value.get()
    after_hits = llm_judge_cache_hits_total._value.get()
    assert after_req - before_req == 1  # only one real judge model call
    assert after_hits - before_hits == 1


@pytest.mark.asyncio
async def test_atp4_024_and_025_cache_key_changes(client, session_factory):
    from app.core.metrics import llm_judge_requests_total

    before = llm_judge_requests_total._value.get()
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    # Run 1 uses rubric v1.
    cfg1 = _judge_cfg(judge_model, rubric["id"])
    run1 = await _create_eval(client, headers, org, project, env, model, version, cfg1)
    await _execute(session_factory, run1["id"])
    # Run 2 uses rubric v2 (same content -> key must differ).
    rubric2 = await _create_rubric(client, headers, org, project, name="QA v2")
    cfg2 = _judge_cfg(judge_model, rubric2["id"])
    run2 = await _create_eval(client, headers, org, project, env, model, version, cfg2)
    await _execute(session_factory, run2["id"])
    # Run 3 uses a different judge model (same rubric -> key must differ).
    judge2 = await _create_model(
        client,
        headers,
        org,
        project,
        (await _create_provider(client, headers, org)),
        config={"local_content": JUDGE_HIGH},
        name="judge2",
    )
    cfg3 = _judge_cfg(judge2, rubric["id"])
    run3 = await _create_eval(client, headers, org, project, env, model, version, cfg3)
    await _execute(session_factory, run3["id"])
    after = llm_judge_requests_total._value.get()
    assert after - before == 3  # no cache reuse across rubric/model changes


@pytest.mark.asyncio
async def test_atp4_026_combined_deterministic_and_judge(client, session_factory):
    from app.core.metrics import llm_judge_requests_total

    before = llm_judge_requests_total._value.get()
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    evaluators = [
        {"type": "exact_match", "enabled": True},
        {
            "type": "llm_judge",
            "enabled": True,
            "judge_model_id": judge_model,
            "rubric_id": rubric["id"],
            "threshold": 0.75,
            "reference_required": True,
        },
    ]
    cfg = {
        "evaluators": evaluators,
        "execution": {"max_concurrency": 4, "timeout_seconds": 10, "stop_on_error": False},
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    names = {s["evaluator"] for s in results[0]["score"]}
    assert names == {"exact_match", "llm_judge"}  # both scores preserved
    assert results[0]["judge_score"] == pytest.approx(0.89)
    assert llm_judge_requests_total._value.get() - before == 1


@pytest.mark.asyncio
async def test_atp4_027_weighted_combined_score(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    evaluators = [
        {"type": "exact_match", "enabled": True, "weight": 0.3},
        {
            "type": "llm_judge",
            "enabled": True,
            "judge_model_id": judge_model,
            "rubric_id": rubric["id"],
            "threshold": 0.75,
            "reference_required": True,
            "weight": 0.7,
        },
    ]
    cfg = {
        "evaluators": evaluators,
        "execution": {
            "max_concurrency": 4,
            "timeout_seconds": 10,
            "stop_on_error": False,
            "pass_policy": "WEIGHTED",
            "threshold": 0.75,
        },
    }
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    # exact 1.0 * 0.3 + judge 0.89 * 0.7 = 0.3 + 0.623 = 0.923
    assert results[0]["combined_score"] == pytest.approx(0.923, abs=0.001)
    assert results[0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_atp4_028_reasoning_stored_not_in_audit(client, session_factory):
    from sqlalchemy import select

    from app.models import AuditLog

    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    reasoning = results[0]["judge_reasoning"]
    assert reasoning  # stored on the result
    async with session_factory() as session:
        rows = (await session.execute(select(AuditLog.action, AuditLog.metadata_))).all()
    for _, meta in rows:
        if meta and reasoning in str(meta):
            raise AssertionError("Judge reasoning leaked into audit metadata")


@pytest.mark.asyncio
async def test_atp4_029_030_031_032_snapshots(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["judge_model_snapshot"]["model_identifier"] == JUDGE_IDENT  # AT-P4-029
    assert got["judge_rubric_snapshot"]["version"] == 1  # AT-P4-030
    assert got["judge_prompt_version"] == "1.0.0"  # AT-P4-031
    assert got["evaluator_versions"]["llm_judge"] == "1.0.0"  # AT-P4-032
    await _execute(session_factory, run["id"])
    results = await _results(client, headers, org, run["id"])
    assert results[0]["judge_model_snapshot"]["model_identifier"] == JUDGE_IDENT


@pytest.mark.asyncio
async def test_atp4_033_034_judge_metrics(client, session_factory):
    from app.core.metrics import (
        llm_judge_duration_seconds,
        llm_judge_requests_total,
        llm_judge_tokens_total,
    )

    before_req = llm_judge_requests_total._value.get()
    before_tokens = llm_judge_tokens_total._value.get()
    before_duration = llm_judge_duration_seconds._sum.get()
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    assert llm_judge_requests_total._value.get() > before_req
    assert llm_judge_tokens_total._value.get() > before_tokens
    assert llm_judge_duration_seconds._sum.get() > before_duration


@pytest.mark.asyncio
async def test_atp4_035_judge_audit_events(client, session_factory):
    from sqlalchemy import select

    from app.models import AuditLog

    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("q1", f"{TARGET_ACTUAL}q1")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
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
    assert "LLM_JUDGE_EVALUATION_STARTED" in actions
    assert "LLM_JUDGE_EVALUATION_COMPLETED" in actions


@pytest.mark.asyncio
async def test_atp4_036_judge_failure_continues(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client,
        [("a", f"{TARGET_ACTUAL}a"), ("b", f"{TARGET_ACTUAL}b")],
        judge_content=JUDGE_MALFORMED,
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["error_tests"] == got["total_tests"]  # both processed despite errors


@pytest.mark.asyncio
async def test_atp4_037_judge_failure_stop_on_error(client, session_factory):
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client,
        [("a", f"{TARGET_ACTUAL}a"), ("b", f"{TARGET_ACTUAL}b"), ("c", f"{TARGET_ACTUAL}c")],
        judge_content=JUDGE_MALFORMED,
    )
    cfg = _judge_cfg(judge_model, rubric["id"], stop_on_error=True, max_concurrency=1)
    run = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run["id"])
    got = (
        await client.get(
            f"/api/v1/evaluations/{run['id']}", headers={**headers, "X-Organization-Id": org}
        )
    ).json()["data"]
    assert got["status"] == "COMPLETED"
    assert got["completed_tests"] < got["total_tests"]  # scheduling stopped


@pytest.mark.asyncio
async def test_atp4_038_cross_org_cache_isolation(client, session_factory):
    from app.core.metrics import llm_judge_requests_total

    before = llm_judge_requests_total._value.get()
    headers, org, project, env, model, version, judge_model, rubric = await _setup(
        client, [("same", f"{TARGET_ACTUAL}same")]
    )
    cfg = _judge_cfg(judge_model, rubric["id"])
    run_a = await _create_eval(client, headers, org, project, env, model, version, cfg)
    await _execute(session_factory, run_a["id"])

    headers_b, org_b, project_b, env_b, model_b, version_b, judge_model_b, rubric_b = await _setup(
        client, [("same", f"{TARGET_ACTUAL}same")], email=OTHER2
    )
    cfg_b = _judge_cfg(judge_model_b, rubric_b["id"])
    run_b = await _create_eval(
        client, headers_b, org_b, project_b, env_b, model_b, version_b, cfg_b
    )
    await _execute(session_factory, run_b["id"])
    after = llm_judge_requests_total._value.get()
    assert after - before == 2  # identical content but different org -> no leak


@pytest.mark.asyncio
async def test_rubric_update_unused_succeeds(client):
    headers, org, project = await _ctx(client)
    rubric = await _create_rubric(client, headers, org, project, name="Draft")
    resp = await client.patch(
        f"/api/v1/rubrics/{rubric['id']}",
        json={"name": "Draft v2", "description": "updated"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Draft v2"


@pytest.mark.asyncio
async def test_rubric_archive(client):
    headers, org, project = await _ctx(client)
    rubric = await _create_rubric(client, headers, org, project, name="Archivable")
    resp = await client.delete(
        f"/api/v1/rubrics/{rubric['id']}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 204
    got = await client.get(
        f"/api/v1/rubrics/{rubric['id']}", headers={**headers, "X-Organization-Id": org}
    )
    assert got.json()["data"]["status"] == "ARCHIVED"
