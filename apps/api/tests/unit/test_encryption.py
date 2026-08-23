"""Credential encryption tests (spec §17–§19; AT-P1-003/004)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.encryption import (
    EncryptionError,
    decrypt_credentials,
    encrypt_credentials,
    mask_secret,
)


def test_encrypt_decrypt_roundtrip():
    plain = "sk-secret-value-12345"
    encrypted = encrypt_credentials(plain)
    assert encrypted != plain
    assert decrypt_credentials(encrypted) == plain


def test_encrypted_blob_is_not_plaintext():
    plain = "sk-9876543210abcdef"
    encrypted = encrypt_credentials(plain)
    assert plain not in encrypted


def test_encrypt_is_deterministic_salt():
    # Fernet ciphertexts differ due to random IV even for identical input.
    a = encrypt_credentials("same")
    b = encrypt_credentials("same")
    assert a != b
    assert decrypt_credentials(a) == decrypt_credentials(b) == "same"


def test_mask_secret_shows_tail():
    masked = mask_secret("sk-abcdef1234567890")
    assert "sk-abcdef1234567890" not in masked
    assert masked.endswith("7890")
    assert "*" in masked


def test_mask_empty():
    assert mask_secret("") == ""


def test_missing_key_raises(monkeypatch):
    # encryption.py binds `get_settings` at import time, so patch it there.
    monkeypatch.setattr(
        "app.core.encryption.get_settings", lambda: Settings(credential_encryption_key="")
    )
    with pytest.raises(EncryptionError):
        encrypt_credentials("x")
