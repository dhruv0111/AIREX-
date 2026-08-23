"""Configuration tests (spec §73 — configuration)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_are_sane():
    settings = Settings(
        app_env="development",
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        jwt_secret_key="a-secret",
    )
    assert settings.app_name == "airex"
    assert settings.app_env == "development"
    assert settings.api_port == 8000
    assert settings.access_token_expire_minutes == 30
    assert settings.is_development is True
    assert settings.is_sqlite is False


def test_cors_origins_parsed():
    settings = Settings(api_cors_origins="http://a.test,http://b.test")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_sqlite_detection():
    settings = Settings(database_url="sqlite+aiosqlite:///./x.db")
    assert settings.is_sqlite is True


def test_required_environment_validation():
    # JWT secret is required for a meaningful deployment: empty value is rejected.
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key="")  # type: ignore[arg-type]


def test_invalid_configuration_handling():
    with pytest.raises(ValidationError):
        Settings(access_token_expire_minutes="not-a-number")  # type: ignore[arg-type]
