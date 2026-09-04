#!/usr/bin/env bash
set -euo pipefail

# AIREX — Automated PostgreSQL Local Backup with SHA-256 Checksum
NAMESPACE="airex-free"
BACKUP_DIR=${BACKUP_DIR:-"/var/airex/backups"}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/airex_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "=== Creating AIREX Database Backup ==="
echo "Target File: ${BACKUP_FILE}"

PG_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=postgres -o jsonpath='{.items[0].metadata.name}')

if [ -z "${PG_POD}" ]; then
    echo "ERROR: PostgreSQL pod not found in ${NAMESPACE}"
    exit 1
fi

# Stream pg_dump through gzip and write locally
START_TIME=$(date +%s%N)
kubectl exec -n "${NAMESPACE}" "${PG_POD}" -- pg_dump -U airex -d airex | gzip > "${BACKUP_FILE}"
END_TIME=$(date +%s%N)

# Calculate SHA-256 Checksum
sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"

DURATION_MS=$(( (END_TIME - START_TIME) / 1000000 ))
FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "=== Backup Created Successfully! ==="
echo "Size: ${FILE_SIZE}"
echo "Duration: ${DURATION_MS} ms"
echo "Checksum: $(cat "${BACKUP_FILE}.sha256")"
