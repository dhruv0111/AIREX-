#!/usr/bin/env bash
# AIREX Production PostgreSQL Restore & Disaster Recovery Script
# Usage: ./scripts/restore_postgres.sh <backup_dump_file>
set -euo pipefail

BACKUP_FILE="${1:-}"

if [ -z "${BACKUP_FILE}" ]; then
  echo "ERROR: Missing backup file argument." >&2
  echo "Usage: $0 <path_to_dump_file>" >&2
  exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "ERROR: Backup file does not exist: ${BACKUP_FILE}" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL environment variable is not set." >&2
  exit 1
fi

# Verify checksum if companion file exists
if [ -f "${BACKUP_FILE}.sha256" ]; then
  echo "==> Verifying SHA-256 integrity..."
  sha256sum -c "${BACKUP_FILE}.sha256"
  echo "==> Checksum verified."
fi

echo "==> Starting database restore to ${DATABASE_URL}..."
# Run pg_restore with clean (--clean) and no-owner (--no-owner)
pg_restore --clean --no-owner --if-exists -d "${DATABASE_URL}" "${BACKUP_FILE}"

echo "==> Database restore completed successfully."
