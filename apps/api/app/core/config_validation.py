"""Production environment and configuration startup hardening validation (Phase 16)."""

from __future__ import annotations

import base64
import logging
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger("airex.config.validation")


class ConfigurationValidationError(RuntimeError):
    """Raised when application startup configuration violates production safety rules."""
    pass


def validate_production_configuration(settings: Settings | None = None) -> dict[str, Any]:
    """Validates configuration settings, raising ConfigurationValidationError if production safety is violated."""
    if settings is None:
        settings = get_settings()

    is_prod = settings.app_env.lower() in {"production", "prod", "staging"}
    results: dict[str, Any] = {
        "environment": settings.app_env,
        "is_production": is_prod,
        "valid": True,
        "checks": [],
    }

    insecure_jwt_secrets = {
        "change-me-to-a-long-random-secret",
        "secret",
        "default",
        "password",
        "demo-password-123",
        "airex_production_super_secret_jwt_key_minimum_32_bytes_long",
    }

    # 1. Check JWT secret
    jwt_secret = settings.jwt_secret_key
    if is_prod:
        if not jwt_secret or jwt_secret in insecure_jwt_secrets or len(jwt_secret) < 32:
            msg = "Production error: JWT_SECRET_KEY must be configured with a secure random key of at least 32 characters."
            results["checks"].append({"name": "jwt_secret", "status": "FAILED", "error": msg})
            raise ConfigurationValidationError(msg)
    results["checks"].append({"name": "jwt_secret", "status": "PASSED"})

    # 2. Check Credential Encryption Key
    enc_key = settings.credential_encryption_key
    if is_prod:
        if not enc_key:
            msg = "Production error: CREDENTIAL_ENCRYPTION_KEY must be provided in production."
            results["checks"].append({"name": "encryption_key", "status": "FAILED", "error": msg})
            raise ConfigurationValidationError(msg)
        try:
            raw_bytes = base64.b64decode(enc_key)
            if len(raw_bytes) != 32:
                msg = "Production error: CREDENTIAL_ENCRYPTION_KEY must be a 32-byte url-safe base64 string."
                results["checks"].append({"name": "encryption_key", "status": "FAILED", "error": msg})
                raise ConfigurationValidationError(msg)
        except Exception:
            msg = "Production error: CREDENTIAL_ENCRYPTION_KEY is not valid base64."
            results["checks"].append({"name": "encryption_key", "status": "FAILED", "error": msg})
            raise ConfigurationValidationError(msg)
    results["checks"].append({"name": "encryption_key", "status": "PASSED"})

    # 3. Check CORS Origins
    origins = settings.cors_origins
    if is_prod and ("*" in origins or not origins):
        msg = "Production error: Wildcard or empty API_CORS_ORIGINS is forbidden in production."
        results["checks"].append({"name": "cors_origins", "status": "FAILED", "error": msg})
        raise ConfigurationValidationError(msg)
    results["checks"].append({"name": "cors_origins", "status": "PASSED"})

    # 4. Check Database URL
    if not settings.database_url:
        msg = "Configuration error: DATABASE_URL is missing."
        results["checks"].append({"name": "database_url", "status": "FAILED", "error": msg})
        raise ConfigurationValidationError(msg)
    results["checks"].append({"name": "database_url", "status": "PASSED"})

    # 5. Check Logging Level
    results["checks"].append({
        "name": "logging",
        "status": "PASSED",
        "details": {"log_level": settings.log_level},
    })

    return results
