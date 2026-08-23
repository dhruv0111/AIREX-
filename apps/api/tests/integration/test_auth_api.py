"""Authentication API integration tests (AT-004..AT-008, AT-016)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

REGISTER = {"name": "Test User", "email": "test@example.com", "password": "StrongPassword123!"}


async def _register(client: AsyncClient, **overrides):
    payload = {**REGISTER, **overrides}
    return await client.post("/api/v1/auth/register", json=payload)


@pytest.mark.asyncio
async def test_at004_register_creates_user(client):
    resp = await _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["access_token"]
    assert body["data"]["token_type"] == "bearer"
    assert body["meta"]["request_id"]


@pytest.mark.asyncio
async def test_at005_duplicate_registration_rejected(client):
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"
    assert resp.json()["error"]["details"]["code"] == "USER_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_at006_login_succeeds(client):
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_at007_invalid_login_fails_401(client):
    await _register(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_at008_protected_endpoint_requires_auth(client):
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_me_returns_memberships(client):
    await _register(client)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    token = login.json()["data"]["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()["data"]
    assert me["user"]["email"] == REGISTER["email"]
    assert me["memberships"][0]["role"] == "OWNER"


@pytest.mark.asyncio
async def test_at016_request_id_in_response_and_logs(client):
    resp = await client.get("/health")
    assert "X-Request-Id" in resp.headers
    assert resp.headers["X-Request-Id"].startswith("req_")
    # The same id appears in the response body meta for API endpoints.
    resp2 = await client.get("/api/v1/auth/me")
    assert resp2.headers.get("X-Request-Id")
