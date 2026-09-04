#!/usr/bin/env bash
set -euo pipefail

# AIREX — Execute Database Migrations inside API Pod
NAMESPACE="airex-free"

echo "=== Running Alembic Migrations in k3s (${NAMESPACE}) ==="

API_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')

if [ -z "${API_POD}" ]; then
    echo "ERROR: No running API pod found in namespace ${NAMESPACE}"
    exit 1
fi

echo "Found active API pod: ${API_POD}"
echo "Executing 'alembic upgrade head'..."
kubectl exec -n "${NAMESPACE}" "${API_POD}" -c api -- alembic upgrade head

echo "=== Migrations Applied Successfully! ==="
