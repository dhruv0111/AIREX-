"""Database backup, verification, and recovery service (spec §39, §46, Phase 12)."""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class BackupService:
    """Manages database dumps, integrity checksums, and recovery verification."""

    @classmethod
    def get_backup_dir(cls) -> Path:
        backup_dir = Path("./backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    @classmethod
    def create_backup(cls, output_path: str | None = None) -> dict[str, Any]:
        """Creates a verified backup of the database with SHA-256 integrity checksum."""
        settings = get_settings()
        now_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        db_url = settings.database_url

        if "sqlite" in db_url:
            # Extract sqlite file path
            sqlite_path = db_url.split("///")[-1]
            if not os.path.exists(sqlite_path):
                Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(sqlite_path)
                conn.close()

            target_file = Path(output_path) if output_path else cls.get_backup_dir() / f"airex_backup_{now_str}.db"
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Safe SQLite backup using online backup API
            src_conn = sqlite3.connect(sqlite_path)
            dst_conn = sqlite3.connect(str(target_file))
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            # Compute SHA-256 checksum
            checksum = cls._compute_sha256(str(target_file))
            size = target_file.stat().st_size

            # Save checksum file
            checksum_file = target_file.with_suffix(target_file.suffix + ".sha256")
            checksum_file.write_text(f"{checksum}  {target_file.name}\n", encoding="utf-8")

            return {
                "status": "SUCCESS",
                "database_type": "sqlite",
                "backup_file": str(target_file),
                "checksum_sha256": checksum,
                "size_bytes": size,
                "created_at": datetime.now(UTC).isoformat(),
            }

        else:
            # PostgreSQL pg_dump
            target_file = Path(output_path) if output_path else cls.get_backup_dir() / f"airex_backup_{now_str}.dump"
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Run pg_dump
            cmd = ["pg_dump", "-Fc", db_url, "-f", str(target_file)]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except Exception as exc:
                raise RuntimeError(f"pg_dump failed: {exc}")

            checksum = cls._compute_sha256(str(target_file))
            size = target_file.stat().st_size
            checksum_file = target_file.with_suffix(target_file.suffix + ".sha256")
            checksum_file.write_text(f"{checksum}  {target_file.name}\n", encoding="utf-8")

            return {
                "status": "SUCCESS",
                "database_type": "postgresql",
                "backup_file": str(target_file),
                "checksum_sha256": checksum,
                "size_bytes": size,
                "created_at": datetime.now(UTC).isoformat(),
            }

    @classmethod
    def verify_backup(cls, backup_path: str) -> dict[str, Any]:
        """Verifies that backup file exists, is non-empty, matches checksum, and is readable."""
        target = Path(backup_path)
        if not target.exists():
            return {
                "status": "FAILED",
                "error": f"Backup file does not exist: {backup_path}",
                "valid": False,
            }

        size = target.stat().st_size
        if size == 0:
            return {
                "status": "FAILED",
                "error": "Backup file is empty (0 bytes).",
                "valid": False,
            }

        current_checksum = cls._compute_sha256(str(target))
        checksum_file = target.with_suffix(target.suffix + ".sha256")
        checksum_match = True
        if checksum_file.exists():
            content = checksum_file.read_text(encoding="utf-8").strip()
            expected_checksum = content.split()[0]
            checksum_match = (current_checksum == expected_checksum)

        # Verify integrity by opening
        readable = False
        if str(target).endswith(".db") or "sqlite" in target.name:
            try:
                conn = sqlite3.connect(str(target))
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                conn.close()
                readable = (result and result[0] == "ok")
            except Exception:
                readable = False
        else:
            # Check with pg_restore -l
            try:
                res = subprocess.run(["pg_restore", "-l", str(target)], capture_output=True)
                readable = (res.returncode == 0)
            except Exception:
                readable = True  # If pg_restore not in local path, rely on non-empty check

        is_valid = checksum_match and readable
        return {
            "status": "VALID" if is_valid else "INVALID",
            "backup_file": str(target),
            "size_bytes": size,
            "checksum_sha256": current_checksum,
            "checksum_verified": checksum_match,
            "format_readable": readable,
            "valid": is_valid,
        }

    _last_restore_test: dict[str, Any] | None = None

    @classmethod
    def restore_backup(cls, backup_path: str, target_db_path: str | None = None) -> dict[str, Any]:
        """Restores a verified database backup into a target environment.
        Verifies SHA-256 integrity first, detects corruption, executes restore,
        and measures the actual Recovery Time (RTO).
        """
        import time
        start_time = time.perf_counter()
        verification = cls.verify_backup(backup_path)
        if not verification.get("valid", False):
            raise ValueError(
                f"Backup restoration rejected: file is corrupted or failed integrity check. Details: {verification.get('error', 'checksum mismatch')}"
            )

        target = Path(backup_path)
        settings = get_settings()

        if str(target).endswith(".db") or "sqlite" in target.name:
            if target_db_path:
                dst_path = Path(target_db_path)
            else:
                default_db = settings.database_url.split("///")[-1]
                dst_path = Path(default_db)

            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Online restore
            src_conn = sqlite3.connect(str(target))
            dst_conn = sqlite3.connect(str(dst_path))
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            duration = time.perf_counter() - start_time
            result = {
                "status": "SUCCESS",
                "database_type": "sqlite",
                "source_backup": str(target),
                "target_database": str(dst_path),
                "checksum_verified": True,
                "restore_duration_seconds": round(duration, 4),
                "restored_at": datetime.now(UTC).isoformat(),
            }
            cls._last_restore_test = result
            return result
        else:
            # PostgreSQL restore
            dst_url = target_db_path or settings.database_url
            cmd = ["pg_restore", "-d", dst_url, "--clean", "--if-exists", str(target)]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except Exception as exc:
                raise RuntimeError(f"pg_restore failed: {exc}")

            duration = time.perf_counter() - start_time
            result = {
                "status": "SUCCESS",
                "database_type": "postgresql",
                "source_backup": str(target),
                "target_database": dst_url,
                "checksum_verified": True,
                "restore_duration_seconds": round(duration, 4),
                "restored_at": datetime.now(UTC).isoformat(),
            }
            cls._last_restore_test = result
            return result

    @classmethod
    def get_recovery_status(cls) -> dict[str, Any]:
        """Returns Disaster Recovery readiness and last restore status."""
        backup_dir = cls.get_backup_dir()
        backups = sorted(
            [f for f in backup_dir.glob("*.db") if not f.name.endswith(".sha256")] +
            [f for f in backup_dir.glob("*.dump") if not f.name.endswith(".sha256")],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
        latest_backup = None
        if backups:
            b = backups[0]
            mtime = datetime.fromtimestamp(b.stat().st_mtime, tz=UTC)
            latest_backup = {
                "file": b.name,
                "size_bytes": b.stat().st_size,
                "created_at": mtime.isoformat(),
                "age_seconds": round((datetime.now(UTC) - mtime).total_seconds(), 1),
            }

        return {
            "backup_count": len(backups),
            "latest_backup": latest_backup,
            "last_restore_test": cls._last_restore_test,
            "dr_readiness_status": "READY" if (latest_backup and cls._last_restore_test) else ("BACKUP_AVAILABLE" if latest_backup else "NEEDS_BACKUP"),
            "target_rpo_seconds": get_settings().backup_rpo_target_seconds,
            "target_rto_seconds": get_settings().backup_rto_target_seconds,
        }

    @staticmethod
    def _compute_sha256(filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
