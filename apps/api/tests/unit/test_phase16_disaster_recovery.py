"""Unit tests for Phase 16 Disaster Recovery, Backup & Restore Validation."""

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.backup_service import BackupService


def test_disaster_recovery_backup_and_restore(tmp_path):
    # 1. Create a dummy sqlite database with sample data
    src_db = tmp_path / "source.db"
    conn = sqlite3.connect(str(src_db))
    cur = conn.cursor()
    cur.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, name TEXT, org_id TEXT);")
    cur.execute("INSERT INTO test_data (name, org_id) VALUES ('record_1', 'org_alpha');")
    cur.execute("INSERT INTO test_data (name, org_id) VALUES ('record_2', 'org_beta');")
    conn.commit()
    conn.close()

    backup_file = tmp_path / "backup.db"

    with patch("app.services.backup_service.get_settings") as mock_settings:
        mock_settings.return_value.database_url = f"sqlite+aiosqlite:///{src_db}"
        mock_settings.return_value.backup_rpo_target_seconds = 3600
        mock_settings.return_value.backup_rto_target_seconds = 1800

        # 2. Create verified backup
        res_backup = BackupService.create_backup(str(backup_file))
        assert res_backup["status"] == "SUCCESS"
        assert os.path.exists(res_backup["backup_file"])
        assert "checksum_sha256" in res_backup

        # 3. Verify backup
        res_verify = BackupService.verify_backup(str(backup_file))
        assert res_verify["valid"] is True
        assert res_verify["checksum_verified"] is True
        assert res_verify["format_readable"] is True

        # 4. Test corruption detection: tamper with the backup file
        corrupted_file = tmp_path / "corrupted_backup.db"
        content = backup_file.read_bytes()
        # Flip bytes in the middle
        corrupted_content = content[:-10] + b"CORRUPTED!"
        corrupted_file.write_bytes(corrupted_content)
        # Copy the original checksum file
        sha_file = corrupted_file.with_suffix(corrupted_file.suffix + ".sha256")
        sha_file.write_text(f"{res_backup['checksum_sha256']}  {corrupted_file.name}\n")

        res_tampered = BackupService.verify_backup(str(corrupted_file))
        assert res_tampered["valid"] is False
        assert res_tampered["checksum_verified"] is False

        # Attempting restore on corrupted backup must raise ValueError
        with pytest.raises(ValueError, match="corrupted or failed integrity check"):
            BackupService.restore_backup(str(corrupted_file), str(tmp_path / "never_created.db"))

        # 5. Execute full database restore into clean target
        target_db = tmp_path / "restored.db"
        res_restore = BackupService.restore_backup(str(backup_file), str(target_db))
        assert res_restore["status"] == "SUCCESS"
        assert os.path.exists(res_restore["target_database"])
        assert res_restore["restore_duration_seconds"] >= 0.0

        # 6. Verify data integrity & tenant isolation after restore
        restored_conn = sqlite3.connect(str(target_db))
        r_cur = restored_conn.cursor()
        r_cur.execute("SELECT name, org_id FROM test_data ORDER BY id ASC;")
        rows = r_cur.fetchall()
        restored_conn.close()

        assert len(rows) == 2
        assert rows[0] == ("record_1", "org_alpha")
        assert rows[1] == ("record_2", "org_beta")

        # 7. Check disaster recovery status telemetry
        status = BackupService.get_recovery_status()
        assert status["dr_readiness_status"] in {"READY", "BACKUP_AVAILABLE"}
        assert status["last_restore_test"] is not None
        assert status["target_rpo_seconds"] == 3600
        assert status["target_rto_seconds"] == 1800
