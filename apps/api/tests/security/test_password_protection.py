"""Password protection tests (AT-030)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import User

PASSWORD = "PlainPassword123!"


@pytest.mark.asyncio
async def test_at030_password_not_stored_in_plaintext(
    client, session_factory: async_sessionmaker[AsyncSession]
):
    await client.post(
        "/api/v1/auth/register",
        json={"name": "S", "email": "s@example.com", "password": PASSWORD},
    )
    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.email == "s@example.com"))
        ).scalar_one()
        assert user.password_hash != PASSWORD
        assert PASSWORD not in user.password_hash
        assert user.password_hash.startswith("pbkdf2_sha256$")
