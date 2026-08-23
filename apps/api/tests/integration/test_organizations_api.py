"""Organization API integration tests (AT-009, AT-010)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

USER_A = {"name": "User A", "email": "a@example.com", "password": "StrongPassword123!"}


async def _auth_headers(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_at009_organization_creation_makes_owner(client):
    await client.post("/api/v1/auth/register", json=USER_A)
    headers = await _auth_headers(client, USER_A["email"], USER_A["password"])
    resp = await client.post(
        "/api/v1/organizations", json={"name": "Org A", "slug": "org-a"}, headers=headers
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["slug"] == "org-a"

    # Owner membership is visible via /me.
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert any(m["role"] == "OWNER" for m in me.json()["data"]["memberships"])


@pytest.mark.asyncio
async def test_at010_organization_isolation(client):
    # Register two users in separate orgs.
    await client.post("/api/v1/auth/register", json=USER_A)
    user_b = {"name": "User B", "email": "b@example.com", "password": "StrongPassword123!"}
    await client.post("/api/v1/auth/register", json=user_b)

    headers_a = await _auth_headers(client, USER_A["email"], USER_A["password"])
    headers_b = await _auth_headers(client, user_b["email"], user_b["password"])

    org_a = await client.post(
        "/api/v1/organizations", json={"name": "Org A", "slug": "org-a"}, headers=headers_a
    )
    org_a_id = org_a.json()["data"]["id"]

    # User B cannot read Org A -> 404 (hidden).
    resp = await client.get(f"/api/v1/organizations/{org_a_id}", headers=headers_b)
    assert resp.status_code == 404
    assert "Org A" not in resp.text
