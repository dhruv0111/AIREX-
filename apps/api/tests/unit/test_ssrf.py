"""SSRF protection tests (spec §52)."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationFailure
from app.core.ssrf import validate_base_url


def test_public_https_url_allowed():
    assert validate_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"


def test_unsupported_protocol_rejected():
    with pytest.raises(ValidationFailure):
        validate_base_url("file:///etc/passwd")


def test_loopback_rejected():
    with pytest.raises(ValidationFailure):
        validate_base_url("http://127.0.0.1:8000")


def test_cloud_metadata_rejected():
    with pytest.raises(ValidationFailure):
        validate_base_url("http://169.254.169.254/latest/meta-data")


def test_private_rfc1918_rejected():
    with pytest.raises(ValidationFailure):
        validate_base_url("http://192.168.1.1")


def test_localhost_rejected():
    with pytest.raises(ValidationFailure):
        validate_base_url("http://localhost:8080")


def test_allow_local_flag():
    assert validate_base_url("http://localhost:11434", allow_local=True) == "http://localhost:11434"
