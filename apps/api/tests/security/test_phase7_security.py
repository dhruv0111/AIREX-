"""Security and multi-tenant isolation boundary tests (Phase 7)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, UTC
from uuid import UUID, uuid4

from tests.integration._helpers import create_project, headers_for, org_id, register
from app.models.ci import ServiceToken

EMAIL_A = "sec_a@example.com"
EMAIL_B = "sec_b@example.com"


@pytest.mark.asyncio
async def test_cross_project_isolation(client: AsyncClient) -> None:
    # 1. Register User A and create Project A
    await register(client, EMAIL_A)
    headers_a = await headers_for(client, EMAIL_A)
    org_a = await org_id(client, headers_a)
    project_a = await create_project(client, headers_a, org_a, name="Project A")

    # 2. Register User B and create Project B (separate account / organization)
    await register(client, EMAIL_B)
    headers_b = await headers_for(client, EMAIL_B)
    org_b = await org_id(client, headers_b)
    project_b = await create_project(client, headers_b, org_b, name="Project B")

    # 3. Create service token for Project A
    payload = {
        "name": "Project A Token",
        "scopes": ["experiments:read"],
    }
    resp = await client.post(
        f"/api/v1/projects/{project_a}/service-tokens",
        json=payload,
        headers={**headers_a, "X-Organization-Id": org_a},
    )
    assert resp.status_code == 201, resp.text
    token_a = resp.json()["data"]["raw_token"]

    # 4. Accessing Project B using Project A's service token must fail with 403 or 404 (isolation boundary)
    ci_headers = {
        "Authorization": f"Bearer {token_a}",
        "X-Organization-Id": org_a,
    }
    resp_b = await client.get(
        f"/api/v1/projects/{project_b}/experiments",
        headers=ci_headers,
    )
    assert resp_b.status_code in (403, 404)


@pytest.mark.asyncio
async def test_revoked_and_expired_token_denials(
    client: AsyncClient,
    session_factory,
) -> None:
    # 1. Create a service token for Project A
    await register(client, "sec_denial@example.com")
    headers = await headers_for(client, "sec_denial@example.com")
    org = await org_id(client, headers)
    project_id = await create_project(client, headers, org, name="Project Denial")

    payload = {
        "name": "Testing Token",
        "scopes": ["experiments:read"],
    }
    resp = await client.post(
        f"/api/v1/projects/{project_id}/service-tokens",
        json=payload,
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text
    raw_token = resp.json()["data"]["raw_token"]
    token_id = resp.json()["data"]["id"]

    # 2. Make it expired directly in the database
    async with session_factory() as session:
        token_model = await session.get(ServiceToken, UUID(token_id))
        assert token_model is not None
        token_model.expires_at = datetime.now(UTC) - timedelta(days=1)
        await session.commit()

    # Requesting with expired token must return 401
    headers_expired = {
        "Authorization": f"Bearer {raw_token}",
        "X-Organization-Id": org,
    }
    resp_expired = await client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers=headers_expired,
    )
    assert resp_expired.status_code == 401

    # 3. Create another token and revoke it directly in the DB
    resp_rev = await client.post(
        f"/api/v1/projects/{project_id}/service-tokens",
        json=payload,
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp_rev.status_code == 201
    raw_token_rev = resp_rev.json()["data"]["raw_token"]
    token_id_rev = resp_rev.json()["data"]["id"]

    async with session_factory() as session:
        token_model_rev = await session.get(ServiceToken, UUID(token_id_rev))
        assert token_model_rev is not None
        token_model_rev.revoked_at = datetime.now(UTC)
        await session.commit()

    # Requesting with revoked token must return 401
    headers_revoked = {
        "Authorization": f"Bearer {raw_token_rev}",
        "X-Organization-Id": org,
    }
    resp_rev_call = await client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers=headers_revoked,
    )
    assert resp_rev_call.status_code == 401
