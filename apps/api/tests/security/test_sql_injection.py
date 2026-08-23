"""SQL injection protection tests (AT-031)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

INJECTIONS = [
    "x' OR '1'='1",
    "'; DROP TABLE users; --",
    'x" OR 1=1 --',
    "admin'--",
]


@pytest.mark.asyncio
async def test_at031_sql_injection_in_email(client: AsyncClient):
    for payload in INJECTIONS:
        resp = await client.post(
            "/api/v1/auth/register",
            json={"name": "I", "email": f"{payload}@x.com", "password": "StrongPassword123!"},
        )
        # No SQL error leaks; either created or validation-conflicted — never 500 with SQL text.
        assert resp.status_code in (201, 409, 400)
        assert "syntax" not in resp.text.lower()


@pytest.mark.asyncio
async def test_at031_sql_injection_in_org_and_project(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"name": "I", "email": "inj@x.com", "password": "StrongPassword123!"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "inj@x.com", "password": "StrongPassword123!"}
    )
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me.json()["data"]["memberships"][0]["organization_id"]

    for idx, payload in enumerate(INJECTIONS):
        org_resp = await client.post(
            "/api/v1/organizations",
            json={"name": payload, "slug": f"safe-slug-{idx}"},
            headers=headers,
        )
        assert org_resp.status_code in (201, 409)

        proj_resp = await client.post(
            "/api/v1/projects",
            json={"name": payload, "slug": f"safe-slug-{idx}"},
            headers={**headers, "X-Organization-Id": org_id},
        )
        assert proj_resp.status_code in (201, 400)
        assert "syntax" not in proj_resp.text.lower()
