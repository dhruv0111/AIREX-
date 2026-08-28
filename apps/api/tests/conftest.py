"""Test fixtures.

Each test gets an isolated SQLite database (aiosqlite) with the API's
``get_db`` dependency overridden, giving real API → service → repository →
database coverage. PostgreSQL-backed integration is exercised by the Docker
test stack (see docker-compose.test.yml).
"""

from __future__ import annotations

import os
import tempfile

# Configure isolated test settings before any app module is imported.
from cryptography.fernet import Fernet

_tmp_dir = tempfile.mkdtemp(prefix="airex-test-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp_dir}/module.db"
os.environ["REDIS_URL"] = "memory://"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-tests-0123456789"
os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["APP_ENV"] = "test"
# Phase 2: isolate dataset storage and keep limits small for fast, safe tests.
os.environ["DATASET_STORAGE_DIR"] = os.path.join(_tmp_dir, "datasets")
os.environ["DATASET_MAX_FILE_SIZE_MB"] = "1"
os.environ["DATASET_MAX_RECORDS"] = "100"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401  (register models)
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest_asyncio.fixture
async def engine(tmp_path):
    """A fresh, per-test SQLite database file (full isolation)."""
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    yield async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the process-global in-memory rate limiter and task queue between tests."""
    from app.core.ratelimit import get_rate_limiter
    from app.workers.queue import InMemoryTaskQueue

    get_rate_limiter().reset()
    InMemoryTaskQueue.reset()
    yield
    get_rate_limiter().reset()
    InMemoryTaskQueue.reset()
