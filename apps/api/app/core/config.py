"""Typed application configuration (Phase 0).

All configuration is loaded through pydantic-settings. Services must not call
``os.getenv`` directly — they receive these settings (see ADR-003 / spec §52).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_name: str = "airex"
    app_version: str = "0.1.0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"

    # Database (async)
    database_url: str = "sqlite+aiosqlite:///./data/airex.db"

    # Redis / queue
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    # Observability
    log_level: str = "INFO"
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    prometheus_enabled: bool = True

    # AI providers (optional in Phase 0; local implementation used when empty)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Seed (development only)
    seed_demo_password: str = "demo-password-123"

    # ---- Phase 1: provider credential encryption ----
    # Fernet key (base64, 32 bytes). NEVER commit the real value.
    credential_encryption_key: str = ""

    # ---- Phase 1: model invocation safety ----
    model_invoke_timeout_seconds: int = 30
    model_max_tokens_max: int = 32768
    model_max_tokens_default: int = 1024
    model_temperature_max: float = 2.0

    # ---- Phase 1: rate limiting (requests per window seconds) ----
    rate_limit_login: int = 5
    rate_limit_login_window: int = 60
    rate_limit_register: int = 10
    rate_limit_register_window: int = 3600
    rate_limit_model_test: int = 30
    rate_limit_model_invoke: int = 60
    rate_limit_model_window: int = 60

    # ---- Phase 2: dataset storage & import limits ----
    dataset_storage_dir: str = "./data/datasets"
    dataset_max_file_size_mb: int = 25
    dataset_max_records: int = 10000

    # ---- Phase 3: evaluation execution ----
    evaluation_max_concurrency: int = 5
    evaluation_timeout_seconds: int = 30
    evaluation_stale_timeout_seconds: int = 600

    # ---- Phase 5: test generation ----
    generation_timeout_seconds: int = 60
    generation_stale_timeout_seconds: int = 600

    @field_validator("jwt_secret_key")
    @classmethod
    def _jwt_secret_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("JWT_SECRET_KEY must not be empty")
        return v

    @field_validator("api_cors_origins")
    @classmethod
    def _parse_origins(cls, v: str) -> list[str]:
        return [o.strip() for o in v.split(",") if o.strip()]

    @property
    def cors_origins(self) -> list[str]:
        raw = self.api_cors_origins
        if isinstance(raw, str):
            return [o.strip() for o in raw.split(",") if o.strip()]
        return list(raw)

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
