"""Credential encryption at rest (spec §17–§19, §51; ADR-010).

Provider credentials are encrypted with Fernet (AES-128-CBC + HMAC). The key
comes from the ``CREDENTIAL_ENCRYPTION_KEY`` environment variable and is never
committed. The API never returns plaintext credentials.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class EncryptionError(Exception):
    """Raised when encryption/decryption cannot be performed."""


def _fernet() -> Fernet:
    key = get_settings().credential_encryption_key
    if not key:
        raise EncryptionError(
            "CREDENTIAL_ENCRYPTION_KEY is not configured. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt_credentials(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_credentials(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise EncryptionError("Unable to decrypt credentials (key mismatch or corrupt data).")


def mask_secret(value: str) -> str:
    """Return a safe masked representation: ``****abcd`` (spec §18)."""
    if not value:
        return ""
    tail = value[-4:]
    prefix = "*" * min(len(value), 16)
    return f"{prefix}{tail}"
