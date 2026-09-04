"""Unit tests for Phase 12 production deployment, secret manager, and readiness checks."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4
import pytest

from app.core.secret_manager import SecretManager, mask_secret, redact_sensitive_dict
from app.models.session import UserSession
from app.models.worker import TaskFailure, WorkerHeartbeat
from app.services.backup_service import BackupService
from app.services.system_readiness import ReadinessCheckResult, SystemReadinessService


def test_mask_secret():
    assert mask_secret("sk-proj-1234567890abcdef") == "sk-****cdef"
    assert mask_secret("short") == "****"
    assert mask_secret("") == ""
    assert mask_secret(None) == ""


def test_redact_sensitive_dict():
    data = {
        "user": "alice",
        "api_key": "sk-secret-12345678",
        "jwt_secret": "super_secret_signing_key_32bytes",
        "nested": {
            "password": "my_password_999",
            "normal_field": "visible_value",
        },
        "items": [{"auth_token": "token_abc123"}, {"count": 42}],
    }
    redacted = redact_sensitive_dict(data)
    assert redacted["user"] == "alice"
    assert "sk-****" in redacted["api_key"]
    assert "sup****" in redacted["jwt_secret"]
    assert "my_****" in redacted["nested"]["password"]
    assert redacted["nested"]["normal_field"] == "visible_value"
    assert "tok****" in redacted["items"][0]["auth_token"]
    assert redacted["items"][1]["count"] == 42


def test_secret_manager_encryption():
    assert SecretManager.validate_key() is True
    plaintext = "super-sensitive-api-token-value"
    encrypted = SecretManager.encrypt(plaintext)
    assert encrypted != plaintext
    assert len(encrypted) > 20

    decrypted = SecretManager.decrypt(encrypted)
    assert decrypted == plaintext


def test_secret_manager_invalid_ciphertext():
    assert SecretManager.decrypt("invalid-garbage-token") == ""
    assert SecretManager.decrypt("") == ""


def test_readiness_check_result_to_dict():
    result = ReadinessCheckResult(
        name="test_service",
        status="HEALTHY",
        severity="INFO",
        description="Everything is running smoothly.",
        latency_ms=12.345,
        details={"version": 1},
    )
    d = result.to_dict()
    assert d["name"] == "test_service"
    assert d["status"] == "HEALTHY"
    assert d["severity"] == "INFO"
    assert d["latency_ms"] == 12.35
    assert d["details"]["version"] == 1


def test_worker_models():
    now = datetime.now(UTC)
    hb = WorkerHeartbeat(
        worker_id="test-worker-1",
        hostname="host-1",
        pid=12345,
        status="ACTIVE",
        active_jobs_count=2,
        heartbeat_at=now,
        started_at=now,
    )
    assert hb.worker_id == "test-worker-1"
    assert hb.status == "ACTIVE"

    tf = TaskFailure(
        job_id="job-99",
        task_name="test_evaluation",
        payload={"eval_id": "xyz"},
        error_message="Connection timed out",
        failed_at=now,
    )
    assert tf.job_id == "job-99"
    assert tf.error_message == "Connection timed out"


def test_backup_service_sqlite_backup_and_verify(tmp_path):
    # Create dummy sqlite database
    import sqlite3
    db_file = tmp_path / "test_airex.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test_tbl (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO test_tbl (name) VALUES ('airex_record');")
    conn.commit()
    conn.close()

    # Point settings database_url to this sqlite file
    from unittest.mock import patch
    with patch("app.services.backup_service.get_settings") as mock_settings:
        mock_settings.return_value.database_url = f"sqlite+aiosqlite:///{db_file}"
        target_backup = tmp_path / "backup_out.db"
        res = BackupService.create_backup(str(target_backup))

        assert res["status"] == "SUCCESS"
        assert os.path.exists(res["backup_file"])
        assert len(res["checksum_sha256"]) == 64

        verify_res = BackupService.verify_backup(str(target_backup))
        assert verify_res["status"] == "VALID"
        assert verify_res["valid"] is True
        assert verify_res["checksum_verified"] is True
        assert verify_res["format_readable"] is True
