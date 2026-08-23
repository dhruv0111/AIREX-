"""Security primitives (spec §59, AT-004/007/029/030).

Phase 0 uses PBKDF2-HMAC-SHA256 (stdlib-only, memory-safe, no native build
required) through a pluggable PasswordHasher so argon2id can be adopted in a
later phase without changing call sites.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import jwt

from app.core.config import Settings

_PBKDF2_ITERATIONS = 600_000
_ALGORITHM = "pbkdf2_sha256"


class PasswordHasher(Protocol):
    def hash_password(self, password: str) -> str: ...

    def verify_password(self, password: str, hashed: str) -> bool: ...


class Pbkdf2PasswordHasher:
    """Password hashing using PBKDF2-HMAC-SHA256 with per-password salt."""

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
        return "{}${}${}${}".format(
            _ALGORITHM,
            _PBKDF2_ITERATIONS,
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )

    def verify_password(self, password: str, hashed: str) -> bool:
        try:
            algorithm, iterations, salt_b64, digest_b64 = hashed.split("$")
            if algorithm != _ALGORITHM:
                return False
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(digest_b64)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False


def create_token(
    settings: Settings,
    *,
    subject: str,
    token_type: str,
    expires_minutes: int,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
        "jti": secrets.token_hex(16),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(settings: Settings, token: str) -> dict[str, Any]:
    """Decode and validate a JWT; raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def create_access_token(
    settings: Settings, user_id: str, *, extra: dict[str, Any] | None = None
) -> str:
    return create_token(
        settings,
        subject=user_id,
        token_type="access",
        expires_minutes=settings.access_token_expire_minutes,
        extra=extra,
    )


def create_refresh_token(settings: Settings, user_id: str) -> str:
    return create_token(
        settings,
        subject=user_id,
        token_type="refresh",
        expires_minutes=settings.refresh_token_expire_minutes,
    )


# ---------------------------------------------------------------------------
# Secret masking (AT-029): prevent API keys / passwords from reaching logs.
# ---------------------------------------------------------------------------
_CREDENTIAL_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),  # OpenAI-style keys
    re.compile(r"(\bBearer\s+[A-Za-z0-9._\-]{8,}\b)", re.IGNORECASE),
    re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?[^"\',\s}]{8,})', re.IGNORECASE),
]


def mask_secrets(value: str) -> str:
    """Replace credential-like substrings with a masked placeholder."""
    for pattern in _CREDENTIAL_PATTERNS:
        value = pattern.sub(lambda m: m.group(1)[:4] + "****", value)
    return value


def new_request_id() -> str:
    return "req_" + secrets.token_hex(6)
