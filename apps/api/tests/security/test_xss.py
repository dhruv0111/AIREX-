"""XSS protection tests (AT-032)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg/onload=alert(1)>",
]


@pytest.mark.asyncio
async def test_at032_xss_payloads_are_stored_as_data_not_rendered(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"name": "X", "email": "xss@x.com", "password": "StrongPassword123!"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "xss@x.com", "password": "StrongPassword123!"}
    )
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    org_id = me.json()["data"]["memberships"][0]["organization_id"]

    for idx, payload in enumerate(XSS_PAYLOADS):
        resp = await client.post(
            "/api/v1/projects",
            json={"name": payload, "slug": f"safe-{idx}"},
            headers={**headers, "X-Organization-Id": org_id},
        )
        assert resp.status_code == 201
        # The API returns JSON data (not HTML); the value is preserved as a
        # plain string for the frontend to escape. No raw HTML is injected.
        assert resp.headers["content-type"].startswith("application/json")
        assert '"name":"' in resp.text or payload in resp.text
        # React/Next.js escapes by default; this test guards the API contract.
        assert resp.text.startswith("{")
