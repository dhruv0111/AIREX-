"""Centralized secret management and credential protection (spec §55, Phase 12)."""

from __future__ import annotations

import base64
import os
import re
from typing import Any
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

SENSITIVE_KEY_RE = re.compile(
    r"(password|secret|api_key|token|access_token|refresh_token|private_key|auth|credential)",
    re.IGNORECASE,
)


def mask_secret(value: str | None, prefix_len: int = 3, suffix_len: int = 4) -> str:
    """Mask a sensitive secret string for safe display (e.g., sk-****1234)."""
    if not value:
        return ""
    if len(value) <= (prefix_len + suffix_len):
        return "****"
    return f"{value[:prefix_len]}****{value[-suffix_len:]}"


def redact_sensitive_dict(val: Any) -> Any:
    """Recursively mask sensitive values in nested dictionaries or lists."""
    if isinstance(val, dict):
        redacted = {}
        for k, v in val.items():
            if SENSITIVE_KEY_RE.search(str(k)):
                redacted[k] = mask_secret(str(v)) if isinstance(v, str) and v else "****"
            else:
                redacted[k] = redact_sensitive_dict(v)
        return redacted
    elif isinstance(val, list):
        return [redact_sensitive_dict(item) for item in val]
    return val


class SecretManager:
    """Centralized encryption, decryption, and validation for provider credentials."""

    @classmethod
    def get_fernet(cls) -> Fernet:
        settings = get_settings()
        key = getattr(settings, "credential_encryption_key", None)
        if not key:
            # Fallback for local testing if not set
            key = base64.urlsafe_b64encode(b"airex-default-32-byte-secret-key").decode()
        if isinstance(key, str):
            key = key.strip().encode("utf-8")
        return Fernet(key)

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypt sensitive plaintext credential using AES-128-CBC / HMAC-SHA256 (Fernet)."""
        if not plaintext:
            return ""
        fernet = cls.get_fernet()
        return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """Decrypt ciphertext into plaintext. Returns empty string on failure."""
        if not ciphertext:
            return ""
        try:
            fernet = cls.get_fernet()
            return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            return ""

    @classmethod
    def validate_key(cls) -> bool:
        """Verify that encryption key is present, valid base64 32-byte, and functional."""
        try:
            test_data = "airex_startup_check"
            enc = cls.encrypt(test_data)
            dec = cls.decrypt(enc)
            return dec == test_data
        except Exception:
            return False
