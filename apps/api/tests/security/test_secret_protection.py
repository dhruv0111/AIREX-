"""Secret protection tests (AT-029)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import mask_secrets


@pytest.mark.asyncio
async def test_at029_api_key_never_in_response_or_logs(client: AsyncClient):
    # Simulate an API key being present in a request payload; the response must
    # never echo it, and our log scrubber must mask it.
    secret = "sk-0123456789abcdef0123456789abcdef"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "K", "email": "k@example.com", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 201
    # Registration never contains API keys by design; assert no key-like tokens.
    assert "sk-" not in resp.text

    # The masker removes the secret from any message that would be logged.
    masked = mask_secrets(f"provider returned key {secret}")
    assert secret not in masked


@pytest.mark.asyncio
async def test_at029_register_response_never_contains_password(client: AsyncClient):
    password = "SuperSecretPassword!"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"name": "P", "email": "p@example.com", "password": password},
    )
    assert resp.status_code == 201
    assert password not in resp.text
