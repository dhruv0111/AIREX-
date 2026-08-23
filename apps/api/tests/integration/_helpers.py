"""Shared integration-test helpers."""

from __future__ import annotations

from httpx import AsyncClient

PASSWORD = "StrongPassword123!"


async def register(client: AsyncClient, email: str, name: str = "Test User") -> None:
    resp = await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text


async def headers_for(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def org_id(client: AsyncClient, headers: dict) -> str:
    me = await client.get("/api/v1/auth/me", headers=headers)
    return me.json()["data"]["memberships"][0]["organization_id"]


async def create_project(
    client: AsyncClient, headers: dict, org: str, name: str = "Demo", slug: str | None = None
) -> str:
    payload = {"name": name, "slug": slug or name.lower().replace(" ", "-")}
    resp = await client.post(
        "/api/v1/projects", json=payload, headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]
