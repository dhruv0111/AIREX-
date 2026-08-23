"""Project API integration tests (AT-011..AT-015)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.permissions import Role
from app.models import OrganizationMember

USER_A = {"name": "User A", "email": "a@example.com", "password": "StrongPassword123!"}
USER_B = {"name": "User B", "email": "b@example.com", "password": "StrongPassword123!"}
PROJECT_PAYLOAD = {
    "name": "Demo RAG Assistant",
    "description": "desc",
    "application_type": "rag_chatbot",
}


async def _register(client, payload: dict) -> dict:
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    return resp.json()["data"]


async def _headers(client, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _org_id(client, headers: dict) -> str:
    me = await client.get("/api/v1/auth/me", headers=headers)
    return me.json()["data"]["memberships"][0]["organization_id"]


@pytest.mark.asyncio
async def test_at011_create_project(client):
    await _register(client, USER_A)
    headers = await _headers(client, USER_A["email"], USER_A["password"])
    org_id = await _org_id(client, headers)
    resp = await client.post(
        "/api/v1/projects", json=PROJECT_PAYLOAD, headers={**headers, "X-Organization-Id": org_id}
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["organization_id"] == org_id
    assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_at012_cross_org_project_hidden(client):
    await _register(client, USER_A)
    await _register(client, USER_B)
    headers_a = await _headers(client, USER_A["email"], USER_A["password"])
    headers_b = await _headers(client, USER_B["email"], USER_B["password"])
    org_a = await _org_id(client, headers_a)
    org_b = await _org_id(client, headers_b)

    created = await client.post(
        "/api/v1/projects", json=PROJECT_PAYLOAD, headers={**headers_a, "X-Organization-Id": org_a}
    )
    project_id = created.json()["data"]["id"]

    # User B, in Org B, cannot read Org A's project -> 404, no data leaked.
    resp = await client.get(
        f"/api/v1/projects/{project_id}", headers={**headers_b, "X-Organization-Id": org_b}
    )
    assert resp.status_code == 404
    assert "Demo RAG Assistant" not in resp.text


@pytest.mark.asyncio
async def test_at013_viewer_cannot_delete_project(
    client, session_factory: async_sessionmaker[AsyncSession]
):
    await _register(client, USER_A)
    await _register(client, USER_B)
    headers_a = await _headers(client, USER_A["email"], USER_A["password"])
    headers_b = await _headers(client, USER_B["email"], USER_B["password"])
    org_a = await _org_id(client, headers_a)
    await _org_id(client, headers_b)

    created = await client.post(
        "/api/v1/projects", json=PROJECT_PAYLOAD, headers={**headers_a, "X-Organization-Id": org_a}
    )
    project_id = created.json()["data"]["id"]

    # Grant User B a VIEWER membership in Org A (test setup through the DB layer).
    async with session_factory() as session:
        session.add(
            OrganizationMember(
                organization_id=UUID(org_a),
                user_id=UUID(
                    (await client.get("/api/v1/auth/me", headers=headers_b)).json()["data"]["user"][
                        "id"
                    ]
                ),
                role=str(Role.VIEWER),
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    # Viewer cannot delete (AT-013) -> 403.
    resp = await client.delete(
        f"/api/v1/projects/{project_id}", headers={**headers_b, "X-Organization-Id": org_a}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_at014_admin_can_update_project(client):
    await _register(client, USER_A)
    headers = await _headers(client, USER_A["email"], USER_A["password"])
    org_id = await _org_id(client, headers)
    created = await client.post(
        "/api/v1/projects", json=PROJECT_PAYLOAD, headers={**headers, "X-Organization-Id": org_id}
    )
    project_id = created.json()["data"]["id"]
    resp = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Renamed"},
        headers={**headers, "X-Organization-Id": org_id},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Renamed"


@pytest.mark.asyncio
async def test_at015_error_format_standard(client):
    resp = await client.post(
        "/api/v1/projects", json={"name": ""}, headers={"Authorization": "Bearer invalid"}
    )
    # Unauthenticated takes precedence: standard error envelope.
    error = resp.json()["error"]
    assert set(("code", "message", "request_id")) <= set(error.keys())
