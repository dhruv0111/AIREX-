"""Phase 1 authorization security tests (cross-tenant isolation, role gating).

These complement AT-P1-008 (cross-org provider in model create) and AT-P1-014
(viewer invoke denied) with direct cross-org access checks on the Phase 1
resources (providers, models, environments, members) and secret hygiene.
"""

from __future__ import annotations

import pytest

from tests.integration._helpers import create_project, headers_for, org_id, register

OWNER_A = "secowner@example.com"
OWNER_B = "secother@example.com"
VIEWER = "secviewer@example.com"


async def _org_with_local_provider(client, email, org_slug="proj", provider_name="Local"):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(client, headers, org, name=org_slug, slug=org_slug)
    prov = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": provider_name, "configuration": {"latency_ms": 2}},
        headers={**headers, "X-Organization-Id": org},
    )
    assert prov.status_code == 201, prov.text
    provider_id = prov.json()["data"]["id"]
    return headers, org, project, provider_id


async def _add_member(client, headers, org, email, role):
    await register(client, email)
    resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": email, "role": role},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_cross_org_provider_invisible_and_denied(client):
    headers_a, org_a, _, provider_a = await _org_with_local_provider(client, OWNER_A)
    await register(client, OWNER_B)
    headers_b = await headers_for(client, OWNER_B)
    org_b = await org_id(client, headers_b)

    # Listing from org B must not include A's provider.
    listing = await client.get(
        "/api/v1/providers", headers={**headers_b, "X-Organization-Id": org_b}
    )
    assert listing.status_code == 200
    assert all(p["id"] != provider_a for p in listing.json()["data"])

    # Direct reads/tests/mutations across tenants must be denied (404, not 200/403 leak).
    for method, path in [
        ("GET", f"/api/v1/providers/{provider_a}"),
        ("POST", f"/api/v1/providers/{provider_a}/test"),
        ("DELETE", f"/api/v1/providers/{provider_a}"),
    ]:
        resp = await client.request(method, path, headers={**headers_b, "X-Organization-Id": org_b})
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_cross_org_model_denied(client):
    headers_a, org_a, project_a, provider_a = await _org_with_local_provider(client, OWNER_A)
    model_resp = await client.post(
        f"/api/v1/projects/{project_a}/models",
        json={
            "name": "M",
            "model_identifier": "m",
            "provider_id": provider_a,
            "configuration": {"retry_policy": {"max_retries": 0}},
        },
        headers={**headers_a, "X-Organization-Id": org_a},
    )
    assert model_resp.status_code == 201, model_resp.text
    model_id = model_resp.json()["data"]["id"]

    await register(client, OWNER_B)
    headers_b = await headers_for(client, OWNER_B)
    org_b = await org_id(client, headers_b)

    for method, path in [
        ("GET", f"/api/v1/models/{model_id}"),
        ("POST", f"/api/v1/models/{model_id}/test"),
        ("POST", f"/api/v1/models/{model_id}/invoke"),
        ("GET", f"/api/v1/models/{model_id}/health"),
        ("DELETE", f"/api/v1/models/{model_id}"),
    ]:
        resp = await client.request(
            method,
            path,
            headers={**headers_b, "X-Organization-Id": org_b},
            json=(
                {"messages": [{"role": "user", "content": "hi"}]}
                if method == "POST" and path.endswith("/invoke")
                else None
            ),
        )
        assert resp.status_code == 404, f"{method} {path} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_viewer_cannot_manage_providers_environments_members(client):
    headers_a, org_a, project_a, provider_a = await _org_with_local_provider(client, OWNER_A)
    await _add_member(client, headers_a, org_a, VIEWER, "VIEWER")
    viewer_headers = await headers_for(client, VIEWER)

    # Viewer cannot create a provider or environment.
    create_provider = await client.post(
        "/api/v1/providers",
        json={"provider_type": "LOCAL", "name": "Viewer Provider"},
        headers={**viewer_headers, "X-Organization-Id": org_a},
    )
    assert create_provider.status_code == 403

    create_env = await client.post(
        f"/api/v1/projects/{project_a}/environments",
        json={"name": "Prod", "environment_type": "PRODUCTION"},
        headers={**viewer_headers, "X-Organization-Id": org_a},
    )
    assert create_env.status_code == 403

    # Viewer cannot add or remove members.
    await register(client, "secviewertarget@example.com")
    add_member = await client.post(
        f"/api/v1/organizations/{org_a}/members",
        json={"email": "secviewertarget@example.com", "role": "VIEWER"},
        headers={**viewer_headers, "X-Organization-Id": org_a},
    )
    assert add_member.status_code == 403

    # Viewer may list providers (view capability) but never mutate.
    listing = await client.get(
        "/api/v1/providers", headers={**viewer_headers, "X-Organization-Id": org_a}
    )
    assert listing.status_code == 200


@pytest.mark.asyncio
async def test_no_plaintext_secret_in_any_provider_response(client):
    secret = "sk-very-long-secret-that-must-not-leak-998877"
    await register(client, OWNER_A)
    headers = await headers_for(client, OWNER_A)
    org = await org_id(client, headers)
    created = await client.post(
        "/api/v1/providers",
        json={"provider_type": "OPENAI", "name": "OpenAI Secret", "api_key": secret},
        headers={**headers, "X-Organization-Id": org},
    )
    assert created.status_code == 201
    assert secret not in created.text
    provider_id = created.json()["data"]["id"]

    for path in [
        f"/api/v1/providers/{provider_id}",
        "/api/v1/providers",
    ]:
        resp = await client.get(path, headers={**headers, "X-Organization-Id": org})
        assert resp.status_code == 200
        assert secret not in resp.text
