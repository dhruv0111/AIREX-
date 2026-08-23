"""Member management API tests (AT-P1-019..025)."""

from __future__ import annotations

import pytest

from tests.integration._helpers import headers_for, org_id, register

OWNER = "memberowner@example.com"
ADMIN = "memberadmin@example.com"
ENGINEER = "memberengineer@example.com"
VIEWER = "memberviewer@example.com"


async def _ctx(client):
    await register(client, OWNER)
    headers = await headers_for(client, OWNER)
    org = await org_id(client, headers)
    return headers, org


async def _add(client, headers, org, email, role):
    await register(client, email)
    return await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": email, "role": role},
        headers={**headers, "X-Organization-Id": org},
    )


async def _membership_id(client, headers, org, email):
    resp = await client.get(
        f"/api/v1/organizations/{org}/members", headers={**headers, "X-Organization-Id": org}
    )
    for member in resp.json()["data"]:
        if member["email"] == email:
            return member["membership_id"]
    raise AssertionError(f"member {email} not found")


@pytest.mark.asyncio
async def test_atp1_019_owner_adds_member(client):
    headers, org = await _ctx(client)
    resp = await _add(client, headers, org, ENGINEER, "ENGINEER")
    assert resp.status_code == 201
    assert resp.json()["data"]["role"] == "ENGINEER"


@pytest.mark.asyncio
async def test_atp1_020_admin_adds_permitted_member(client):
    headers, org = await _ctx(client)
    await _add(client, headers, org, ADMIN, "ADMIN")
    admin_headers = await headers_for(client, ADMIN)
    # The target user must exist first (MemberService.add resolves by email).
    await register(client, "newviewer@example.com")
    resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": "newviewer@example.com", "role": "VIEWER"},
        headers={**admin_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_atp1_021_engineer_add_member_denied(client):
    headers, org = await _ctx(client)
    await _add(client, headers, org, ENGINEER, "ENGINEER")
    engineer_headers = await headers_for(client, ENGINEER)
    resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": "x@example.com", "role": "VIEWER"},
        headers={**engineer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_atp1_022_viewer_modify_member_denied(client):
    headers, org = await _ctx(client)
    await _add(client, headers, org, VIEWER, "VIEWER")
    viewer_headers = await headers_for(client, VIEWER)
    resp = await client.post(
        f"/api/v1/organizations/{org}/members",
        json={"email": "y@example.com", "role": "VIEWER"},
        headers={**viewer_headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_atp1_023_remove_final_owner_conflict(client):
    headers, org = await _ctx(client)
    owner_member_id = await _membership_id(client, headers, org, OWNER)
    resp = await client.delete(
        f"/api/v1/organizations/{org}/members/{owner_member_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_atp1_024_change_member_role_with_audit(client):
    headers, org = await _ctx(client)
    await _add(client, headers, org, ENGINEER, "ENGINEER")
    member_id = await _membership_id(client, headers, org, ENGINEER)
    resp = await client.patch(
        f"/api/v1/organizations/{org}/members/{member_id}",
        json={"role": "ADMIN"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_atp1_025_remove_member_with_audit(client):
    headers, org = await _ctx(client)
    await _add(client, headers, org, ENGINEER, "ENGINEER")
    member_id = await _membership_id(client, headers, org, ENGINEER)
    resp = await client.delete(
        f"/api/v1/organizations/{org}/members/{member_id}",
        headers={**headers, "X-Organization-Id": org},
    )
    assert resp.status_code == 204
