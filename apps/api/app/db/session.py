"""Async database engine / session factory (spec §2.1 API-first)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_engine_and_sessionmaker(database_url: str | None = None):
    settings = get_settings()
    url = database_url or settings.database_url
    kwargs = {"echo": False, "pool_pre_ping": True}
    if not url.startswith("sqlite"):
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_timeout"] = settings.db_pool_timeout
        kwargs["pool_recycle"] = settings.db_pool_recycle
    engine = create_async_engine(url, **kwargs)
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine, expire_on_commit=False
    )
    return engine, session_factory


_engine, _session_factory = create_engine_and_sessionmaker()


def get_engine():
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_database() -> bool:
    """Return True if the database is reachable (readiness, AT-002)."""
    try:
        async with _engine.connect() as conn:
            await conn.execute(  # noqa: F841 (execute for connectivity)
                __import__("sqlalchemy").text("SELECT 1")
            )
        return True
    except Exception:
        return False


async def init_models(create_all: bool = False) -> None:
    """Create tables for non-Alembic environments (SQLite dev/tests).

    Production uses Alembic migrations; this is a convenience for tests and
    local SQLite development only.
    """
    if create_all:
        import app.models  # noqa: F401  (register models)
        from app.db.base import Base

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
