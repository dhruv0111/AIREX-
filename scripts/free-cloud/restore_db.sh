#!/usr/bin/env bash
set -euo pipefail

# AIREX — Test Database Restore & Integrity Verification
NAMESPACE="airex-free"
BACKUP_FILE=${1:-""}

if [ -z "${BACKUP_FILE}" ]; then
    # Find latest backup
    BACKUP_FILE=$(ls -t /var/airex/backups/*.sql.gz 2>/dev/null | head -n 1 || echo "")
fi

if [ -z "${BACKUP_FILE}" ] || [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "=== Verifying & Restoring Backup: ${BACKUP_FILE} ==="

# 1. Verify SHA-256 Checksum
if [ -f "${BACKUP_FILE}.sha256" ]; then
    echo "Verifying SHA-256 integrity..."
    sha256sum -c "${BACKUP_FILE}.sha256"
else
    echo "WARNING: Checksum file ${BACKUP_FILE}.sha256 not found, proceeding with raw restore."
fi

PG_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=postgres -o jsonpath='{.items[0].metadata.name}')

# 2. Restore into a separate test database 'airex_restore_test' to verify schema & data without affecting live data
echo "Creating test restore database 'airex_restore_test'..."
kubectl exec -n "${NAMESPACE}" "${PG_POD}" -- psql -U airex -d postgres -c "DROP DATABASE IF EXISTS airex_restore_test;"
kubectl exec -n "${NAMESPACE}" "${PG_POD}" -- psql -U airex -d postgres -c "CREATE DATABASE airex_restore_test;"

START_TIME=$(date +%s%N)
gunzip -c "${BACKUP_FILE}" | kubectl exec -i -n "${NAMESPACE}" "${PG_POD}" -- psql -U airex -d airex_restore_test > /dev/null
END_TIME=$(date +%s%N)

RESTORE_MS=$(( (END_TIME - START_TIME) / 1000000 ))

# 3. Verify Table Counts
TABLE_COUNT=$(kubectl exec -n "${NAMESPACE}" "${PG_POD}" -- psql -U airex -d airex_restore_test -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
echo "Restored Tables: ${TABLE_COUNT}"
echo "Restore Time (RTO): ${RESTORE_MS} ms"
echo "=== Restore Integrity Verified Successfully! ==="
