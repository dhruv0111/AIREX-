"""Focused alert engine unit tests (Phase 8 §75)."""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from sqlalchemy import select

from app.models.alert import AlertRule, Alert
from app.models.trace import Trace, Span
from app.models.project import Project
from app.evaluations.alert_engine import evaluate_alert_rules


async def _setup_project(session_factory, *, webhook_url: str | None = None) -> UUID:
    async with session_factory() as db:
        project = Project(
            id=uuid4(),
            organization_id=uuid4(),
            name="Alert Proj",
            slug=f"alert-{uuid4().hex[:8]}",
            application_type="rag_chatbot",
            status="ACTIVE",
            settings={"webhook_url": webhook_url} if webhook_url else None,
        )
        db.add(project)
        await db.commit()
        return project.id


async def _add_rule(session_factory, project_id: UUID, **kwargs) -> UUID:
    async with session_factory() as db:
        defaults = dict(
            name="Rule",
            metric="error_rate",
            operator=">",
            threshold=0.1,
            duration_seconds=600,
            cooldown_seconds=60,
            severity="HIGH",
            is_enabled=True,
        )
        defaults.update(kwargs)
        rule = AlertRule(id=uuid4(), project_id=project_id, **defaults)
        db.add(rule)
        await db.commit()
        return rule.id


async def _add_traces(session_factory, project_id: UUID, statuses: list[str], *, durations=None) -> None:
    async with session_factory() as db:
        for i, status in enumerate(statuses):
            t = Trace(
                id=uuid4(),
                project_id=project_id,
                organization_id=project_id,
                trace_id=f"t_{uuid4().hex[:12]}",
                status=status,
                duration_ms=durations[i] if durations else None,
                quality_score=0.8 if status == "SUCCESS" else 0.2,
                start_time=datetime.now(UTC) - timedelta(seconds=10),
            )
            db.add(t)
        await db.commit()


@pytest.mark.asyncio
async def test_alert_engine_request_rate_metric(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="request_rate", operator=">", threshold=5.0, duration_seconds=60)
    # 10 requests in 60s -> 10 requests/min > 5
    await _add_traces(session_factory, project_id, ["SUCCESS"] * 10)

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["triggered_alerts"] == 1
        alert = (await db.execute(select(Alert))).scalar_one()
        assert alert.status == "TRIGGERED"


@pytest.mark.asyncio
async def test_alert_engine_latency_p95_metric(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="latency_p95", operator=">", threshold=900.0)
    # durations p95 well above 900ms
    await _add_traces(session_factory, project_id, ["SUCCESS"] * 10, durations=[1000.0 + i * 10 for i in range(10)])

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["triggered_alerts"] == 1
        alert = (await db.execute(select(Alert))).scalar_one()
        assert alert.observed_value > 900.0


@pytest.mark.asyncio
async def test_alert_engine_cost_metric(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="cost", operator=">", threshold=0.5)

    async with session_factory() as db:
        t = Trace(
            id=uuid4(), project_id=project_id, organization_id=project_id,
            trace_id="cost_trace", status="SUCCESS", start_time=datetime.now(UTC) - timedelta(seconds=5),
        )
        db.add(t)
        await db.flush()
        db.add(Span(
            id=uuid4(), trace_id="cost_trace", span_id="cost_span", name="llm",
            span_type="LLM", status="SUCCESS", estimated_cost=1.0,
            start_time=datetime.now(UTC) - timedelta(seconds=5),
        ))
        await db.commit()

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["triggered_alerts"] == 1


@pytest.mark.asyncio
async def test_alert_engine_token_usage_metric(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="token_usage", operator=">", threshold=100)

    async with session_factory() as db:
        t = Trace(
            id=uuid4(), project_id=project_id, organization_id=project_id,
            trace_id="tok_trace", status="SUCCESS", start_time=datetime.now(UTC) - timedelta(seconds=5),
        )
        db.add(t)
        await db.flush()
        db.add(Span(
            id=uuid4(), trace_id="tok_trace", span_id="tok_span", name="llm",
            span_type="LLM", status="SUCCESS", total_tokens=500,
            start_time=datetime.now(UTC) - timedelta(seconds=5),
        ))
        await db.commit()

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["triggered_alerts"] == 1


@pytest.mark.asyncio
async def test_alert_engine_quality_score_metric(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="quality_score", operator="<", threshold=0.5)
    await _add_traces(session_factory, project_id, ["SUCCESS"] * 5)  # quality_score 0.8 -> not triggered

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["triggered_alerts"] == 0


@pytest.mark.asyncio
async def test_alert_engine_operator_variants(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="error_rate", operator=">=", threshold=0.1)
    await _add_traces(session_factory, project_id, ["ERROR"] * 2 + ["SUCCESS"] * 8)  # 20% >= 10%

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["triggered_alerts"] == 1


@pytest.mark.asyncio
async def test_alert_engine_webhook_notification_success(session_factory) -> None:
    project_id = await _setup_project(session_factory, webhook_url="https://hooks.example.com/test")
    await _add_rule(session_factory, project_id, metric="error_rate", operator=">", threshold=0.1)
    await _add_traces(session_factory, project_id, ["ERROR"] * 3 + ["SUCCESS"] * 1)

    with patch(
        "app.evaluations.alert_engine.WebhookNotificationProvider.send_notification",
        new_callable=AsyncMock,
    ) as mock_send:
        async with session_factory() as db:
            result = await evaluate_alert_rules(db)
            assert result["triggered_alerts"] == 1
            mock_send.assert_awaited_once()

        async with session_factory() as db:
            alert = (await db.execute(select(Alert))).scalar_one()
            assert alert.notification_status == "SENT"


@pytest.mark.asyncio
async def test_alert_engine_webhook_notification_failure(session_factory) -> None:
    """AT-P8: notification failure must not break alert state."""
    project_id = await _setup_project(session_factory, webhook_url="https://hooks.example.com/fail")
    await _add_rule(session_factory, project_id, metric="error_rate", operator=">", threshold=0.1)
    await _add_traces(session_factory, project_id, ["ERROR"] * 3 + ["SUCCESS"] * 1)

    with patch(
        "app.evaluations.alert_engine.WebhookNotificationProvider.send_notification",
        new_callable=AsyncMock,
        side_effect=RuntimeError("webhook down"),
    ):
        async with session_factory() as db:
            result = await evaluate_alert_rules(db)
            # Alert still triggered even though notification failed
            assert result["triggered_alerts"] == 1

        async with session_factory() as db:
            alert = (await db.execute(select(Alert))).scalar_one()
            assert alert.status == "TRIGGERED"
            assert alert.notification_status == "FAILED"
            assert alert.notification_error == "webhook down"


@pytest.mark.asyncio
async def test_alert_engine_disabled_rule_skipped(session_factory) -> None:
    project_id = await _setup_project(session_factory)
    await _add_rule(session_factory, project_id, metric="error_rate", operator=">", threshold=0.1, is_enabled=False)
    await _add_traces(session_factory, project_id, ["ERROR"] * 3 + ["SUCCESS"] * 1)

    async with session_factory() as db:
        result = await evaluate_alert_rules(db)
        assert result["evaluated_rules"] == 0
        assert result["triggered_alerts"] == 0


@pytest.mark.asyncio
async def test_webhook_secret_not_leaked() -> None:
    """AT-P8-024: webhook secret must never appear in the request body."""
    from app.services.notifications import WebhookNotificationProvider

    provider = WebhookNotificationProvider("https://hooks.example.com/endpoint")
    secret = "super-secret-hmac-key-123"

    with patch("app.services.notifications.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        payload = {"alert_id": "alert_1", "severity": "HIGH", "metric": "error_rate"}
        await provider.send_notification(payload, secret)

    # Extract what was sent
    _, kwargs = mock_client.post.call_args
    body = kwargs.get("content", "")
    headers = kwargs.get("headers", {})

    # The secret must NOT appear in the body or headers (only as an HMAC signature)
    assert secret not in body
    assert secret not in json.dumps(headers)
    # The HMAC signature header IS present
    assert "X-Airex-Signature" in headers
    assert "X-Airex-Timestamp" in headers
    assert headers["X-Airex-Signature"]
