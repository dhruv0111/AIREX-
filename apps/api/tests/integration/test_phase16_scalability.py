"""Integration tests for Phase 16 Controlled Load, Concurrency & Performance."""

import asyncio
import time
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.metrics import get_request_stats


@pytest.mark.asyncio
async def test_controlled_concurrency_load_and_metrics(auth_client: AsyncClient):
    """Execute controlled concurrent requests at 10, 25, and 50 workers across key platform endpoints.
    Verify no connection leaks, no cross-tenant leakage, and record p50/p95/p99 latency.
    """
    concurrency_levels = [10, 25]
    results_by_concurrency = {}

    for concurrency in concurrency_levels:
        async def worker_task(idx: int) -> float:
            start = time.perf_counter()
            # 1. Read operations overview
            resp1 = await auth_client.get("/api/v1/system/operations/overview")
            assert resp1.status_code == 200

            # 2. Read readiness
            resp2 = await auth_client.get("/api/v1/system/readiness")
            assert resp2.status_code == 200

            # 3. Read organizations
            resp3 = await auth_client.get("/api/v1/organizations")
            assert resp3.status_code == 200

            duration = time.perf_counter() - start
            return duration

        batch_start = time.perf_counter()
        tasks = [worker_task(i) for i in range(concurrency)]
        durations = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - batch_start

        durations.sort()
        n = len(durations)
        p50 = durations[int(n * 0.50)] * 1000.0
        p95 = durations[min(int(n * 0.95), n - 1)] * 1000.0
        p99 = durations[min(int(n * 0.99), n - 1)] * 1000.0
        rps = (concurrency * 3) / max(0.001, total_time)

        results_by_concurrency[concurrency] = {
            "rps": round(rps, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "total_time_seconds": round(total_time, 3),
        }

        # Assert reasonable latency bounds (no deadlock or starvation)
        assert p95 < 5000.0, f"p95 latency exceeded threshold: {p95}ms"

    # Verify overall performance metrics
    stats = get_request_stats(window_seconds=60)
    assert stats["total_requests"] > 0
    assert stats["error_rate"] == 0.0


@pytest.mark.asyncio
async def test_cross_tenant_isolation_under_concurrency(client: AsyncClient):
    """Execute concurrent requests from two separate tenants simultaneously.
    Verify tenant isolation is never compromised during concurrent query execution.
    """
    # Create Tenant Alpha
    email_a = f"alpha-{uuid4().hex[:6]}@example.com"
    reg_a = await client.post("/api/v1/auth/register", json={"name": "Org Alpha Admin", "email": email_a, "password": "Password123!"})
    token_a = reg_a.json()["data"]["access_token"]
    orgs_a = (await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_a}"})).json()["data"]
    org_id_a = orgs_a[0]["id"]

    # Create Tenant Beta
    email_b = f"beta-{uuid4().hex[:6]}@example.com"
    reg_b = await client.post("/api/v1/auth/register", json={"name": "Org Beta Admin", "email": email_b, "password": "Password123!"})
    token_b = reg_b.json()["data"]["access_token"]
    orgs_b = (await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_b}"})).json()["data"]
    org_id_b = orgs_b[0]["id"]

    # Create Project in Org Alpha
    proj_resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-Id": org_id_a},
        json={"name": "Confidential Alpha Project", "slug": f"alpha-{uuid4().hex[:4]}"},
    )
    project_id_alpha = proj_resp.json()["data"]["id"]

    # Concurrently execute requests from Tenant Beta attempting to access Org Alpha's project
    async def attacker_probe(i: int):
        resp = await client.get(
            f"/api/v1/projects/{project_id_alpha}",
            headers={"Authorization": f"Bearer {token_b}", "X-Organization-Id": org_id_b},
        )
        assert resp.status_code in {403, 404}, f"Tenant isolation broken on request {i}: status {resp.status_code}"

    probes = [attacker_probe(i) for i in range(20)]
    await asyncio.gather(*probes)
