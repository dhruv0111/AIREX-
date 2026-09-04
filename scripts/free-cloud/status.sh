#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# AIREX Zero-Cost Cloud Deployment Status Inspector
# Inspects nodes, namespaces, workloads, stateful pods, storage, and health
# ==============================================================================

NAMESPACE=${NAMESPACE:-"airex-free"}
API_HOST=${1:-""}

echo "============================================================"
echo "          AIREX Free Cloud Status Inspector                 "
echo "          Target Namespace: ${NAMESPACE}                    "
echo "============================================================"

# 0. Check cluster connectivity
if ! command -v kubectl >/dev/null 2>&1; then
    echo "ERROR: 'kubectl' is not installed."
    exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "ERROR: Cannot connect to Kubernetes cluster."
    exit 1
fi

# 1. Cluster Nodes
echo "--- 1. Kubernetes Cluster Nodes ---"
kubectl get nodes -o wide

# 2. Namespace Verification
echo ""
echo "--- 2. Namespace Status ---"
if kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
    kubectl get namespace "${NAMESPACE}"
else
    echo "WARNING: Namespace '${NAMESPACE}' does not exist yet. Run deployment script first."
    exit 0
fi

# 3. Workloads & Pods
echo ""
echo "--- 3. Pod Status (${NAMESPACE}) ---"
kubectl get pods -n "${NAMESPACE}" -o wide

# 4. Services
echo ""
echo "--- 4. Cluster Services ---"
kubectl get svc -n "${NAMESPACE}"

# 5. Ingress Configuration
echo ""
echo "--- 5. Ingress Rules ---"
kubectl get ingress -n "${NAMESPACE}"

# 6. Persistent Volume Claims
echo ""
echo "--- 6. Persistent Volume Claims (Storage) ---"
kubectl get pvc -n "${NAMESPACE}"

# 7. Recent Pod Restarts or Failures
echo ""
echo "--- 7. Pod Restart / Failure Audit ---"
RESTARTS=$(kubectl get pods -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.metadata.name}{"\tRestarts: "}{.status.containerStatuses[0].restartCount}{"\n"}{end}' 2>/dev/null || echo "None")
echo "${RESTARTS}"

# 8. Live Health Probes (if API_HOST provided or discovered)
echo ""
echo "--- 8. Live Health Probes ---"
if [ -z "${API_HOST}" ]; then
    PUBLIC_IP=$(curl -s -4 --max-time 3 https://ifconfig.me || curl -s -4 --max-time 3 https://api.ipify.org || echo "127.0.0.1")
    API_HOST="http://api.${PUBLIC_IP}.sslip.io"
fi

echo "Probing Endpoint: ${API_HOST}/health/live"
LIVE_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_HOST}/health/live" 2>/dev/null || echo "UNREACHABLE")
echo "  /health/live HTTP Response: ${LIVE_CODE}"

echo "Probing Endpoint: ${API_HOST}/health/ready"
READY_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${API_HOST}/health/ready" 2>/dev/null || echo "UNREACHABLE")
echo "  /health/ready HTTP Response: ${READY_CODE}"

echo "============================================================"
echo "Status check complete."
