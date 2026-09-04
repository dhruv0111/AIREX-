#!/usr/bin/env bash
# AIREX Production PostgreSQL Backup Script
# Usage: ./scripts/backup_postgres.sh [backup_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/airex_pg_${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

echo "==> Starting AIREX PostgreSQL backup..."
echo "==> Target: ${BACKUP_FILE}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL environment variable is not set." >&2
  exit 1
fi

# Run pg_dump in custom compressed format
pg_dump -Fc "${DATABASE_URL}" -f "${BACKUP_FILE}"

# Generate SHA-256 checksum
sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"

SIZE_BYTES=$(wc -c < "${BACKUP_FILE}")
echo "==> Backup completed successfully (${SIZE_BYTES} bytes)."
echo "==> SHA-256: $(cat "${BACKUP_FILE}.sha256")"
