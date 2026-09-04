"""Security tests for Phase 12: HTTP headers, token reuse detection, and body limits."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    headers = resp.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert "max-age=31536000" in headers.get("strict-transport-security", "")
    assert "default-src 'self'" in headers.get("content-security-policy", "")
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_token_reuse_detection_defense(client: AsyncClient):
    # 1. Register to get initial refresh token
    email = "p12_security_user@example.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "Security User", "email": email, "password": "Password123!"},
    )
    assert reg_resp.status_code == 201
    initial_tokens = reg_resp.json()["data"]
    initial_refresh = initial_tokens["refresh_token"]

    # 2. Legitimate rotation: refresh token is rotated
    first_refresh = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert first_refresh.status_code == 200
    rotated_tokens = first_refresh.json()["data"]

    # 3. Adversary attempts replay of initial_refresh (token reuse attack!)
    adversary_attempt = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    # Must reject!
    assert adversary_attempt.status_code in (401, 403)
    error_msg = adversary_attempt.json()["error"]["message"]
    assert "Token reuse detected" in error_msg or "revoked" in error_msg

    # 4. Invariant: All user sessions must now be invalidated, including the legitimate rotated token
    subsequent_attempt = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated_tokens["refresh_token"]},
    )
    # The rotated token was also revoked due to the breach response
    assert subsequent_attempt.status_code in (401, 403)


@pytest.mark.asyncio
async def test_request_size_limit_rejection(client: AsyncClient):
    # Send request body exceeding 10MB limit via Content-Length
    headers = {"content-length": str(11 * 1024 * 1024)}
    resp = await client.post("/api/v1/auth/login", headers=headers, json={"email": "a", "password": "b"})
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "REQUEST_ENTITY_TOO_LARGE"
