"""Development seed data (spec §54, AT-019).

Creates (idempotently):
  Organization: AIREX Demo
  User:         demo@example.com (OWNER)
  Project:      Demo RAG Assistant

Note: the email must use a real, registerable domain. The API validates
emails with EmailStr, which rejects special-use/reserved TLDs such as
``.local`` on both register and login.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import Pbkdf2PasswordHasher
from app.db.session import get_engine, get_session_factory
from app.models import Organization, OrganizationMember, Project, User

logger = logging.getLogger("airex.seed")

DEMO_EMAIL = "demo@example.com"
DEMO_ORG_SLUG = "airex-demo"
DEMO_PROJECT_SLUG = "demo-rag-assistant"


async def run_seed(session: AsyncSession) -> None:
    from sqlalchemy import select

    hasher = Pbkdf2PasswordHasher()
    settings = get_settings()

    user = (
        await session.execute(select(User).where(User.email == DEMO_EMAIL))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hasher.hash_password(settings.seed_demo_password),
            name="Demo User",
            email_verified=True,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        logger.info("seed: created demo user %s", DEMO_EMAIL)

    org = (
        await session.execute(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    ).scalar_one_or_none()
    if org is None:
        org = Organization(name="AIREX Demo", slug=DEMO_ORG_SLUG)
        session.add(org)
        await session.flush()
        logger.info("seed: created demo organization")

    member = (
        await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        from datetime import datetime

        session.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role=str(Role.OWNER),
                created_at=datetime.now(UTC),
            )
        )
        logger.info("seed: granted OWNER membership")

    project = (
        await session.execute(select(Project).where(Project.slug == DEMO_PROJECT_SLUG))
    ).scalar_one_or_none()
    if project is None:
        project = Project(
            organization_id=org.id,
            name="Demo RAG Assistant",
            slug=DEMO_PROJECT_SLUG,
            description="Seed RAG assistant for local development.",
            application_type="rag_chatbot",
            created_by=user.id,
        )
        session.add(project)
        logger.info("seed: created demo project")

    await session.commit()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    engine = get_engine()
    # Ensure tables exist for a fresh SQLite dev database.
    if get_settings().is_sqlite:
        import app.models  # noqa: F401
        from app.db.base import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    factory = get_session_factory()
    async with factory() as session:
        await run_seed(session)
    await engine.dispose()
    print("Seed complete. Login: demo@example.com")


if __name__ == "__main__":
    asyncio.run(main())
