"""Provider API tests (AT-P1-001..006, 026..028)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Provider
from tests.integration._helpers import headers_for, org_id, register

EMAIL = "provider@example.com"


@pytest.mark.asyncio
async def test_atp1_001_create_local_provider(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local Test", "configuration": {"latency_ms": 5}},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["provider_type"] == "LOCAL"
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_atp1_002_invalid_provider_type_rejected(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "BOGUS", "name": "X"},
        headers={**headers, "X-Organization-Id": org},
    )
    # 400 VALIDATION_ERROR per ERROR_CONTRACTS (request validation errors).
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_atp1_003_credentials_encrypted_in_db(client, session_factory):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    secret = "sk-super-secret-1234567890"
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "OPENAI", "name": "OpenAI", "api_key": secret},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    async with session_factory() as session:
        provider = (
            await session.execute(select(Provider).where(Provider.name == "OpenAI"))
        ).scalar_one()
        assert provider.encrypted_credentials is not None
        assert secret not in provider.encrypted_credentials
        assert provider.credential_version == 1


@pytest.mark.asyncio
async def test_atp1_004_get_provider_never_returns_plaintext(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    secret = "sk-never-returned-abcdef1234"
    created = await client.post(
        "/api/v1/providers",
        json={"provider_type": "OPENAI", "name": "OpenAI2", "api_key": secret},
        headers={**headers, "X-Organization-Id": org},
    )
    provider_id = created.json()["data"]["id"]
    resp = await client.get(
        f"/api/v1/providers/{provider_id}", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert secret not in resp.text
    assert data["masked_key"] is not None
    assert data["masked_key"].endswith(secret[-4:])


@pytest.mark.asyncio
async def test_atp1_005_provider_connection_test_connected(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    created = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Local OK", "configuration": {"latency_ms": 2}},
        headers={**headers, "X-Organization-Id": org},
    )
    provider_id = created.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/providers/{provider_id}/test", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "CONNECTED"


@pytest.mark.asyncio
async def test_atp1_006_provider_test_simulated_failure(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    created = await client.post(
        "/api/v1/providers",
        json={
            "provider_type": "LOCAL",
            "name": "Local Fail",
            "configuration": {"failure_mode": "unavailable"},
        },
        headers={**headers, "X-Organization-Id": org},
    )
    provider_id = created.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/providers/{provider_id}/test", headers={**headers, "X-Organization-Id": org}
    )
    assert resp.status_code == 200
    result = resp.json()["data"]
    assert result["status"] == "UNKNOWN"
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_atp1_026_rotate_credential(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    created = await client.post(
        "/api/v1/providers",
        json={"provider_type": "OPENAI", "name": "Rotate", "api_key": "sk-old-secret-1111111111"},
        headers={**headers, "X-Organization-Id": org},
    )
    provider_id = created.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/providers/{provider_id}/rotate",
        json={"api_key": "sk-new-secret-2222222222"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["masked_key"].endswith("2222")
    assert "sk-new-secret" not in resp.text


@pytest.mark.asyncio
async def test_atp1_027_rotate_invalid_credential_rejected(client):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    created = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "NoRotate"},
        headers={**headers, "X-Organization-Id": org},
    )
    provider_id = created.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/providers/{provider_id}/rotate",
        json={"api_key": "anything"},
        headers={**headers, "X-Organization-Id": org},
    )
    # LOCAL has no credentials to rotate → controlled 400, provider unchanged.
    assert resp.status_code == 400
    get_resp = await client.get(
        f"/api/v1/providers/{provider_id}", headers={**headers, "X-Organization-Id": org}
    )
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_atp1_028_provider_secret_not_in_logs(client, session_factory):
    await register(client, EMAIL)
    headers = await headers_for(client, EMAIL)
    org = await org_id(client, headers)
    secret = "sk-log-leak-check-5555555555"
    resp = await client.post(
        "/api/v1/providers",
        json={"provider_type": "OPENAI", "name": "LogCheck", "api_key": secret},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201
    assert secret not in resp.text
    # Audit metadata must not contain secrets (PROVIDER_CREATED).
    async with session_factory() as session:
        from app.models import AuditLog

        logs = (
            (await session.execute(select(AuditLog).where(AuditLog.action == "PROVIDER_CREATED")))
            .scalars()
            .all()
        )
        for log in logs:
            assert secret not in (log.metadata_ or {}).get("api_key", "")
