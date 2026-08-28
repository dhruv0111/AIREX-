"""Integration and Acceptance Tests for Phase 8 Observability & Alerting."""

from __future__ import annotations

import httpx
from datetime import datetime, timedelta, UTC
from uuid import uuid4, UUID
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.integration._helpers import create_project, headers_for, org_id, register
from app.models.pricing import ModelPricing
from app.models.alert import AlertRule, Alert
from app.models.trace import Trace, Span
from app.evaluations.alert_engine import evaluate_alert_rules
from app.services.observability import ObservabilityService
from app.workers.tasks import clean_observability_retention_for_session

EMAIL = "observability_integration@example.com"


async def _ctx(client: AsyncClient):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name="Obs Proj", slug="obs-proj")
    return headers, org, project


@pytest.mark.asyncio
async def test_observability_ingestion_and_queries(client: AsyncClient, session_factory) -> None:
    headers, org, project_id = await _ctx(client)

    async with session_factory() as db_session:
        # 1. Seed versioned ModelPricing configurations
        pricing1 = ModelPricing(
            id=uuid4(),
            model_pattern="gpt-4o*",
            provider="openai",
            input_price_per_1k=0.005,
            output_price_per_1k=0.015,
            currency="USD",
            effective_from=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.add(pricing1)
        await db_session.commit()

    # 2. Ingest batch of traces & spans via the API (AT-P8-001/002/006/007/009)
    trace_id_1 = f"trace_{uuid4()}"
    span_id_1 = f"span_{uuid4()}"[:16]
    span_id_2 = f"span_{uuid4()}"[:16]

    ingest_payload = {
        "traces": [
            {
                "trace_id": trace_id_1,
                "environment": "production",
                "service_name": "api-gateway",
                "operation_name": "chat-completion",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": (datetime.now(UTC) + timedelta(milliseconds=800)).isoformat(),
                "status": "SUCCESS",
            }
        ],
        "spans": [
            {
                "trace_id": trace_id_1,
                "span_id": span_id_1,
                "parent_span_id": None,
                "name": "root-span",
                "span_type": "CUSTOM",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": (datetime.now(UTC) + timedelta(milliseconds=800)).isoformat(),
                "status": "SUCCESS",
                "duration_ms": 800.0,
            },
            {
                "trace_id": trace_id_1,
                "span_id": span_id_2,
                "parent_span_id": span_id_1,
                "name": "model-call",
                "span_type": "LLM",
                "provider": "openai",
                "model": "gpt-4o-2024-05-13",
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
                "temperature": 0.7,
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": (datetime.now(UTC) + timedelta(milliseconds=500)).isoformat(),
                "status": "SUCCESS",
                "duration_ms": 500.0,
            }
        ],
    }

    # Ingest using user session with X-Project-Id header
    resp = await client.post(
        "/api/v1/observability/ingest",
        json=ingest_payload,
        headers={**headers, "X-Project-Id": str(project_id)},
    )
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    assert job_id is not None

    async with session_factory() as db_session:
        # Since ingestion runs inside background task, wait or run in-process manually to verify db entries
        # In tests, queue is InMemoryTaskQueue, we can run it or call service directly.
        # To test integration cleanly, we call the ObservabilityService directly to ingest:
        service = ObservabilityService(db_session)
        result = await service.ingest_batch(
            project_id=UUID(project_id),
            org_id=UUID(org),
            traces=ingest_payload["traces"],
            spans=ingest_payload["spans"],
        )
        assert result["traces_ingested"] == 1
        assert result["spans_ingested"] == 2

        # Verify Cost Calculations (AT-P8-007: 1000 input tokens * 0.005/1K + 500 output tokens * 0.015/1K = 0.005 + 0.0075 = 0.0125)
        stmt_spans = select(Span).where(Span.trace_id == trace_id_1)
        res_spans = await db_session.execute(stmt_spans)
        db_spans = res_spans.scalars().all()
        llm_span = next(s for s in db_spans if s.span_type == "LLM")
        assert float(llm_span.estimated_cost) == 0.0125

    # 3. Query overview dashboard metrics (AT-P8-004/005/010)
    overview_resp = await client.get(
        f"/api/v1/projects/{project_id}/observability/overview",
        headers=headers,
    )
    assert overview_resp.status_code == 200, overview_resp.text
    overview_data = overview_resp.json()
    assert overview_data["total_requests"] >= 1
    assert overview_data["total_cost"] == 0.0125
    assert overview_data["total_tokens"] == 1500

    # 4. Fetch trace explorer list (AT-P8-004)
    explorer_resp = await client.get(
        f"/api/v1/projects/{project_id}/observability/traces",
        headers=headers,
    )
    assert explorer_resp.status_code == 200, explorer_resp.text
    traces_list = explorer_resp.json()["traces"]
    assert any(t["trace_id"] == trace_id_1 for t in traces_list)

    # 5. Fetch trace details span hierarchy (AT-P8-005)
    details_resp = await client.get(
        f"/api/v1/observability/traces/{trace_id_1}",
        headers=headers,
    )
    assert details_resp.status_code == 200, details_resp.text
    detail_data = details_resp.json()
    assert detail_data["trace"]["trace_id"] == trace_id_1
    assert len(detail_data["spans"]) == 2

    # 6. Quality signals (AT-P8-037/039)
    quality_payload = {
        "trace_id": trace_id_1,
        "signals": {
            "thumbs_up": True,
            "human_rating": 4.5,
        }
    }
    qual_resp = await client.post(
        f"/api/v1/projects/{project_id}/observability/quality-signals",
        json=quality_payload,
        headers=headers,
    )
    assert qual_resp.status_code == 200, qual_resp.text

    # Re-fetch details to verify updated quality score
    details_resp = await client.get(
        f"/api/v1/observability/traces/{trace_id_1}",
        headers=headers,
    )
    assert details_resp.json()["trace"]["quality_score"] == 2.75  # (1.0 + 4.5) / 2 = 2.75


@pytest.mark.asyncio
async def test_pricing_and_privacy_modes(client: AsyncClient, session_factory) -> None:
    headers, org, project_id = await _ctx(client)

    async with session_factory() as db_session:
        # AT-P8-008: Missing pricing returns null cost
        service = ObservabilityService(db_session)
        trace_id = f"trace_{uuid4()}"
        
        # 1. Test missing pricing
        result = await service.ingest_batch(
            project_id=UUID(project_id),
            org_id=UUID(org),
            traces=[{"trace_id": trace_id, "start_time": datetime.now(UTC)}],
            spans=[
                {
                    "trace_id": trace_id,
                    "span_id": "span_unknown",
                    "name": "unknown-model",
                    "span_type": "LLM",
                    "provider": "unknown",
                    "model": "gpt-3.5-turbo-unknown",
                    "input_tokens": 100,
                    "output_tokens": 100,
                    "start_time": datetime.now(UTC),
                }
            ],
        )
        stmt = select(Span).where(Span.trace_id == trace_id)
        res = await db_session.execute(stmt)
        span = res.scalars().first()
        assert span.estimated_cost is None

        # 2. Test Privacy Mode: METADATA_ONLY (Default)
        trace_id_priv = f"trace_{uuid4()}"
        # Default is METADATA_ONLY, prompts/responses inside attributes should be redacted
        result_priv = await service.ingest_batch(
            project_id=UUID(project_id),
            org_id=UUID(org),
            traces=[{"trace_id": trace_id_priv, "start_time": datetime.now(UTC)}],
            spans=[
                {
                    "trace_id": trace_id_priv,
                    "span_id": "span_priv",
                    "name": "llm",
                    "span_type": "LLM",
                    "start_time": datetime.now(UTC),
                    "attributes": {
                        "prompt": "highly sensitive raw user prompt",
                        "response": "confidential llm output response",
                        "user_id": "test_user_1",  # Metadata key, keep it
                    }
                }
            ],
        )
        res_span_priv = await db_session.execute(select(Span).where(Span.trace_id == trace_id_priv))
        span_priv = res_span_priv.scalars().first()
        # Check that prompt and response keys are gone
        assert "prompt" not in span_priv.attributes
        assert "response" not in span_priv.attributes
        assert span_priv.attributes["user_id"] == "test_user_1"


@pytest.mark.asyncio
async def test_alert_rules_evaluation(client: AsyncClient, session_factory) -> None:
    headers, org, project_id = await _ctx(client)

    async with session_factory() as db_session:
        # 1. Create Alert Rule (AT-P8-019)
        rule = AlertRule(
            id=uuid4(),
            project_id=UUID(project_id),
            name="High Error Rate Alert",
            metric="error_rate",
            operator=">",
            threshold=0.2,  # > 20%
            duration_seconds=300,
            cooldown_seconds=600,
            severity="CRITICAL",
            is_enabled=True,
        )
        db_session.add(rule)
        await db_session.commit()

        # 2. Add traces that cross threshold (3 errors, 1 success -> 75% error rate)
        traces = []
        for i in range(3):
            traces.append(
                Trace(
                    id=uuid4(),
                    project_id=UUID(project_id),
                    organization_id=UUID(org),
                    trace_id=f"alert_trace_err_{i}",
                    status="ERROR",
                    start_time=datetime.now(UTC) - timedelta(seconds=10),
                )
            )
        traces.append(
            Trace(
                id=uuid4(),
                project_id=UUID(project_id),
                organization_id=UUID(org),
                trace_id="alert_trace_ok",
                status="SUCCESS",
                start_time=datetime.now(UTC) - timedelta(seconds=10),
            )
        )
        for t in traces:
            db_session.add(t)
        await db_session.commit()

        # 3. Evaluate alerts
        eval_res = await evaluate_alert_rules(db_session)
        assert eval_res["triggered_alerts"] == 1

        # Verify Alert in DB
        stmt_alert = select(Alert).where(Alert.project_id == UUID(project_id))
        res_alert = await db_session.execute(stmt_alert)
        alert = res_alert.scalar_one()
        assert alert.status == "TRIGGERED"
        assert alert.severity == "CRITICAL"
        assert alert.occurrence_count == 1

        # 4. Deduplication check: evaluate alerts again (AT-P8-020)
        # The error condition remains, we expect occurrence_count to increment and not make new Alert rows
        eval_res_2 = await evaluate_alert_rules(db_session)
        assert eval_res_2["triggered_alerts"] == 0  # No new alert triggered
        
        # Reload from DB
        res_alert_2 = await db_session.execute(stmt_alert)
        alert_reload = res_alert_2.scalar_one()
        assert alert_reload.occurrence_count == 2
        assert alert_reload.status == "TRIGGERED"

        # 5. Alert Recovery check: update database to clear error conditions (AT-P8-021)
        # Update traces to all be SUCCESS
        stmt_load_traces = select(Trace).where(Trace.project_id == UUID(project_id))
        res_t = await db_session.execute(stmt_load_traces)
        for t in res_t.scalars().all():
            t.status = "SUCCESS"
        await db_session.commit()

        # Evaluate alerts, should resolve active alert
        eval_res_3 = await evaluate_alert_rules(db_session)
        assert eval_res_3["resolved_alerts"] == 1

        # Reload and check resolved state
        res_alert_3 = await db_session.execute(stmt_alert)
        alert_resolved = res_alert_3.scalar_one()
        assert alert_resolved.status == "RESOLVED"
        assert alert_resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_observability_settings_and_dashboard_breakdowns(client: AsyncClient, session_factory) -> None:
    headers, org, project_id = await _ctx(client)

    # 1. Default settings are privacy-safe (METADATA_ONLY)
    resp = await client.get(f"/api/v1/projects/{project_id}/observability/settings", headers=headers)
    assert resp.status_code == 200, resp.text
    settings = resp.json()
    assert settings["observability_mode"] == "METADATA_ONLY"
    assert settings["sample_rate"] == 1.0

    # 2. Update settings (sampling + retention)
    update_payload = {
        "observability_mode": "HASHED_CONTENT",
        "retention_days": 30,
        "sample_rate": 0.5,
        "capture_errors": True,
        "capture_quality_signals": True,
    }
    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["observability_mode"] == "HASHED_CONTENT"
    assert updated["retention_days"] == 30
    assert updated["sample_rate"] == 0.5

    # 3. Invalid sample rate rejected
    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"sample_rate": 1.5},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    # 4. Invalid observability mode rejected
    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"observability_mode": "EVERYTHING"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    # 4b. Reset sample rate to 1.0 so subsequent ingestion is deterministic
    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"sample_rate": 1.0},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # 5. Seed a trace + LLM span with pricing for dashboard breakdowns
    async with session_factory() as db_session:
        pricing = ModelPricing(
            id=uuid4(),
            model_pattern="gpt-4o*",
            provider="openai",
            input_price_per_1k=0.005,
            output_price_per_1k=0.015,
            effective_from=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.add(pricing)
        await db_session.commit()

    trace_id = f"dash_trace_{uuid4()}"
    ingest_payload = {
        "traces": [
            {
                "trace_id": trace_id,
                "environment": "production",
                "service_name": "api",
                "operation_name": "chat",
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": (datetime.now(UTC) + timedelta(milliseconds=600)).isoformat(),
                "status": "SUCCESS",
                "duration_ms": 600.0,
            }
        ],
        "spans": [
            {
                "trace_id": trace_id,
                "span_id": "dash_span_1",
                "parent_span_id": None,
                "name": "model-call",
                "span_type": "LLM",
                "provider": "openai",
                "model": "gpt-4o-2024-05-13",
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
                "start_time": datetime.now(UTC).isoformat(),
                "end_time": (datetime.now(UTC) + timedelta(milliseconds=400)).isoformat(),
                "status": "SUCCESS",
                "duration_ms": 400.0,
            }
        ],
    }
    async with session_factory() as db_session:
        service = ObservabilityService(db_session)
        await service.ingest_batch(
            project_id=UUID(project_id),
            org_id=UUID(org),
            traces=ingest_payload["traces"],
            spans=ingest_payload["spans"],
        )

    # 6. Models breakdown endpoint
    resp = await client.get(f"/api/v1/projects/{project_id}/observability/models", headers=headers)
    assert resp.status_code == 200, resp.text
    models = resp.json()["models"]
    assert any(m["model"] == "gpt-4o-2024-05-13" for m in models)

    # 7. Providers breakdown endpoint
    resp = await client.get(f"/api/v1/projects/{project_id}/observability/providers", headers=headers)
    assert resp.status_code == 200, resp.text
    providers = resp.json()["providers"]
    assert any(p["provider"] == "openai" for p in providers)

    # 8. Cost endpoint returns actual computed cost (not fake)
    resp = await client.get(f"/api/v1/projects/{project_id}/observability/cost", headers=headers)
    assert resp.status_code == 200, resp.text
    cost = resp.json()
    assert cost["total_cost"] == 0.0125
    assert cost["cost_per_request"] == 0.0125

    # 9. Latency endpoint
    resp = await client.get(f"/api/v1/projects/{project_id}/observability/latency", headers=headers)
    assert resp.status_code == 200, resp.text
    latency = resp.json()
    assert latency["total_requests"] == 1
    assert latency["latency_avg"] == 600.0


@pytest.mark.asyncio
async def test_pricing_api_crud(client: AsyncClient, session_factory) -> None:
    headers, org, project_id = await _ctx(client)

    # 1. Create pricing
    resp = await client.post(
        "/api/v1/pricing",
        json={
            "model_pattern": "claude-3-5-sonnet",
            "provider": "anthropic",
            "input_price_per_1k": 0.003,
            "output_price_per_1k": 0.015,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    pricing_id = resp.json()["id"]

    # 2. List pricing
    resp = await client.get("/api/v1/pricing", headers=headers)
    assert resp.status_code == 200, resp.text
    assert any(p["id"] == pricing_id for p in resp.json())

    # 3. Update pricing
    resp = await client.patch(
        f"/api/v1/pricing/{pricing_id}",
        json={"input_price_per_1k": 0.004},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["input_price_per_1k"] == 0.004

    # 4. Delete pricing
    resp = await client.delete(f"/api/v1/pricing/{pricing_id}", headers=headers)
    assert resp.status_code == 204, resp.text

    # 5. Duplicate model pattern rejected
    await client.post(
        "/api/v1/pricing",
        json={"model_pattern": "gpt-4o*", "provider": "openai", "input_price_per_1k": 0.005, "output_price_per_1k": 0.015},
        headers=headers,
    )
    resp = await client.post(
        "/api/v1/pricing",
        json={"model_pattern": "gpt-4o*", "provider": "openai", "input_price_per_1k": 0.005, "output_price_per_1k": 0.015},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_alert_acknowledgement_api(client: AsyncClient, session_factory) -> None:
    headers, org, project_id = await _ctx(client)

    async with session_factory() as db_session:
        rule = AlertRule(
            id=uuid4(),
            project_id=UUID(project_id),
            name="Ack Rule",
            metric="error_rate",
            operator=">",
            threshold=0.2,
            duration_seconds=300,
            severity="HIGH",
            is_enabled=True,
        )
        db_session.add(rule)
        await db_session.commit()
        rule_id = rule.id

        alert = Alert(
            id=uuid4(),
            alert_rule_id=rule_id,
            project_id=UUID(project_id),
            status="TRIGGERED",
            severity="HIGH",
            message="test alert",
            observed_value=0.5,
            occurrence_count=1,
            triggered_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        db_session.add(alert)
        await db_session.commit()
        alert_id = alert.id

    # Acknowledge via API (AT-P8-022)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/alerts/{alert_id}/ack",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ACKNOWLEDGED"
    assert resp.json()["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_duplicate_span_deduplication(client: AsyncClient, session_factory) -> None:
    """AT-P8-003: duplicate span ingestion must not create duplicate rows."""
    headers, org, project_id = await _ctx(client)
    trace_id = f"dup_trace_{uuid4()}"
    span_id = f"dup_span_{uuid4()}"[:16]

    payload = {
        "traces": [{"trace_id": trace_id, "start_time": datetime.now(UTC), "status": "SUCCESS"}],
        "spans": [{
            "trace_id": trace_id,
            "span_id": span_id,
            "name": "model-call",
            "span_type": "LLM",
            "start_time": datetime.now(UTC),
            "status": "SUCCESS",
        }],
    }

    async with session_factory() as db_session:
        service = ObservabilityService(db_session)
        # Ingest the same trace + span twice (as a retrying client would)
        r1 = await service.ingest_batch(
            project_id=UUID(project_id), org_id=UUID(org),
            traces=list(payload["traces"]), spans=list(payload["spans"]),
        )
        r2 = await service.ingest_batch(
            project_id=UUID(project_id), org_id=UUID(org),
            traces=list(payload["traces"]), spans=list(payload["spans"]),
        )
        assert r1["spans_ingested"] == 1
        assert r2["traces_ingested"] == 0
        assert r2["spans_ingested"] == 0

        count = (await db_session.execute(select(Span).where(Span.trace_id == trace_id))).scalars().all()
        assert len(count) == 1
        count_traces = (await db_session.execute(select(Trace).where(Trace.trace_id == trace_id))).scalars().all()
        assert len(count_traces) == 1


@pytest.mark.asyncio
async def test_sampling_zero_and_one(client: AsyncClient, session_factory) -> None:
    """AT-P8-011/012: sample_rate 0 stores no normal traces; 1 stores all."""
    headers, org, project_id = await _ctx(client)

    # Configure sample_rate = 0
    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"sample_rate": 0.0},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    trace_id_zero = f"zero_{uuid4()}"
    async with session_factory() as db_session:
        service = ObservabilityService(db_session)
        await service.ingest_batch(
            project_id=UUID(project_id), org_id=UUID(org),
            traces=[{"trace_id": trace_id_zero, "start_time": datetime.now(UTC), "status": "SUCCESS"}],
            spans=[],
        )
        res = await db_session.execute(select(Trace).where(Trace.trace_id == trace_id_zero))
        assert res.scalar_one_or_none() is None

    # Configure sample_rate = 1
    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"sample_rate": 1.0},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    trace_id_one = f"one_{uuid4()}"
    async with session_factory() as db_session:
        service = ObservabilityService(db_session)
        await service.ingest_batch(
            project_id=UUID(project_id), org_id=UUID(org),
            traces=[{"trace_id": trace_id_one, "start_time": datetime.now(UTC), "status": "SUCCESS"}],
            spans=[],
        )
        res = await db_session.execute(select(Trace).where(Trace.trace_id == trace_id_one))
        assert res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_error_trace_bypasses_sampling(client: AsyncClient, session_factory) -> None:
    """AT-P8-013: error traces bypass normal sampling when configured."""
    headers, org, project_id = await _ctx(client)

    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"sample_rate": 0.0, "error_bypass_sampling": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    err_trace = f"err_{uuid4()}"
    ok_trace = f"ok_{uuid4()}"
    async with session_factory() as db_session:
        service = ObservabilityService(db_session)
        await service.ingest_batch(
            project_id=UUID(project_id), org_id=UUID(org),
            traces=[
                {"trace_id": err_trace, "start_time": datetime.now(UTC), "status": "ERROR"},
                {"trace_id": ok_trace, "start_time": datetime.now(UTC), "status": "SUCCESS"},
            ],
            spans=[],
        )
        res_err = await db_session.execute(select(Trace).where(Trace.trace_id == err_trace))
        res_ok = await db_session.execute(select(Trace).where(Trace.trace_id == ok_trace))
        assert res_err.scalar_one_or_none() is not None  # error bypassed sampling
        assert res_ok.scalar_one_or_none() is None        # normal trace dropped at rate 0


@pytest.mark.asyncio
async def test_retention_deletes_expired_data(client: AsyncClient, session_factory) -> None:
    """AT-P8-016: retention policy deletes expired traces and spans."""
    headers, org, project_id = await _ctx(client)

    resp = await client.put(
        f"/api/v1/projects/{project_id}/observability/settings",
        json={"retention_days": 7},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    old_trace = f"old_{uuid4()}"
    new_trace = f"new_{uuid4()}"
    async with session_factory() as db_session:
        service = ObservabilityService(db_session)
        await service.ingest_batch(
            project_id=UUID(project_id), org_id=UUID(org),
            traces=[
                {"trace_id": old_trace, "start_time": datetime.now(UTC) - timedelta(days=30), "status": "SUCCESS"},
                {"trace_id": new_trace, "start_time": datetime.now(UTC), "status": "SUCCESS"},
            ],
            spans=[{
                "trace_id": old_trace, "span_id": "old_span", "name": "llm", "span_type": "LLM",
                "start_time": datetime.now(UTC) - timedelta(days=30), "status": "SUCCESS",
            }],
        )

    async with session_factory() as db_session:
        result = await clean_observability_retention_for_session(db_session)
    assert result["deleted_traces"] >= 1

    async with session_factory() as db_session:
        res_old = await db_session.execute(select(Trace).where(Trace.trace_id == old_trace))
        assert res_old.scalar_one_or_none() is None
        res_old_span = await db_session.execute(select(Span).where(Span.trace_id == old_trace))
        assert res_old_span.scalars().all() == []
        res_new = await db_session.execute(select(Trace).where(Trace.trace_id == new_trace))
        assert res_new.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_oversized_ingestion_rejected(client: AsyncClient, session_factory) -> None:
    """AT-P8-029: oversized ingestion payloads are rejected safely."""
    headers, org, project_id = await _ctx(client)

    now = datetime.now(UTC)
    traces = [
        {"trace_id": f"big_{i}", "start_time": now.isoformat(), "status": "SUCCESS"}
        for i in range(1001)  # exceeds max batch of 1000
    ]
    resp = await client.post(
        "/api/v1/observability/ingest",
        json={"traces": traces, "spans": []},
        headers={**headers, "X-Project-Id": str(project_id)},
    )
    assert resp.status_code == 400, resp.text
