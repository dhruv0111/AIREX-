"""Security primitives tests (AT-004/007/029/030)."""

from __future__ import annotations

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    Pbkdf2PasswordHasher,
    create_access_token,
    create_refresh_token,
    decode_token,
    mask_secrets,
)

SETTINGS = Settings(
    jwt_secret_key="unit-test-secret-key-0123456789abcdef",
    database_url="sqlite+aiosqlite:///:memory:",
)


def test_password_hash_and_verify():
    hasher = Pbkdf2PasswordHasher()
    hashed = hasher.hash_password("StrongPassword123!")
    assert hashed != "StrongPassword123!"
    assert "$" in hashed
    assert hasher.verify_password("StrongPassword123!", hashed) is True


def test_password_verify_wrong_password():
    hasher = Pbkdf2PasswordHasher()
    hashed = hasher.hash_password("correct-password")
    assert hasher.verify_password("wrong-password", hashed) is False


def test_password_verify_malformed_hash():
    hasher = Pbkdf2PasswordHasher()
    assert hasher.verify_password("x", "not-a-valid-hash") is False


def test_password_hashes_are_unique_per_salt():
    hasher = Pbkdf2PasswordHasher()
    assert hasher.hash_password("same") != hasher.hash_password("same")


def test_access_token_roundtrip():
    token = create_access_token(SETTINGS, "user-123")
    payload = decode_token(SETTINGS, token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["jti"]


def test_refresh_token_type():
    token = create_refresh_token(SETTINGS, "user-123")
    assert decode_token(SETTINGS, token)["type"] == "refresh"


def test_token_expiry_is_rejected():
    import jwt as pyjwt

    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(
            SETTINGS,
            pyjwt.encode({"sub": "x", "exp": 0}, SETTINGS.jwt_secret_key, algorithm="HS256"),
        )


def test_token_bad_secret_rejected():
    other = Settings(jwt_secret_key="different-secret", database_url="sqlite+aiosqlite:///:memory:")
    token = create_access_token(SETTINGS, "user-1")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(other, token)


def test_secret_masking_hides_api_key():
    message = "calling sk-1234567890abcdef1234 provider"
    masked = mask_secrets(message)
    assert "sk-1234567890abcdef1234" not in masked
    assert "sk-1****" in masked


def test_secret_masking_hides_bearer():
    masked = mask_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
    assert "Bearer eyJhbGciOiJIUzI1NiJ9" not in masked
