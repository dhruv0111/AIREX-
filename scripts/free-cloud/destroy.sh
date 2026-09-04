#!/usr/bin/env bash
set -euo pipefail

# AIREX — Clean Teardown of Free Tier Deployment
NAMESPACE=${NAMESPACE:-"airex-free"}
FORCE=${FORCE:-"false"}

if [ "${1:-}" == "--force" ] || [ "${1:-}" == "-f" ]; then
    FORCE="true"
fi

if [ "${FORCE}" != "true" ] && [ "${CONFIRM_DESTROY:-}" != "yes" ]; then
    echo "WARNING: This will permanently delete namespace '${NAMESPACE}' and all attached PVCs/data."
    read -r -p "Type 'DELETE' to confirm teardown: " CONFIRMATION
    if [ "${CONFIRMATION}" != "DELETE" ]; then
        echo "Teardown aborted."
        exit 0
    fi
fi

echo "=== Deleting AIREX Resources in Namespace: ${NAMESPACE} ==="
kubectl delete namespace "${NAMESPACE}" --timeout=120s || true

echo "=== Teardown Complete ==="
