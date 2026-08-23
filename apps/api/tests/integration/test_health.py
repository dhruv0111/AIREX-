"""Health endpoint tests (AT-025/026/027)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_at025_health_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_at026_liveness_ok(client):
    resp = await client.get("/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_at027_readiness_ok_when_dependencies_healthy(client):
    # SQLite file DB (created by fixture) + memory:// queue = healthy.
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["postgres"] == "ok"
    assert body["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "http_requests_total" in text
    assert "http_request_duration_seconds" in text
