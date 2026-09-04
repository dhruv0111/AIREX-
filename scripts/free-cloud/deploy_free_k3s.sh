#!/usr/bin/env bash
set -euo pipefail

# AIREX — Deploy Zero-Cost k3s Stack
NAMESPACE=${NAMESPACE:-"airex-free"}
PUBLIC_IP_ARG=${1:-""}

echo "=== Deploying AIREX to k3s (Namespace: ${NAMESPACE}) ==="

# 0. Check prerequisites
if ! command -v kubectl >/dev/null 2>&1; then
    echo "ERROR: 'kubectl' command not found. Please install k3s or kubectl first."
    exit 1
fi

if ! kubectl cluster-info >/dev/null 2>&1; then
    echo "ERROR: Cannot connect to Kubernetes cluster. Is k3s running?"
    exit 1
fi

# 1. Detect or use provided public IP for wildcard sslip.io DNS
if [ -n "${PUBLIC_IP_ARG}" ]; then
    PUBLIC_IP="${PUBLIC_IP_ARG}"
elif [ -n "${PUBLIC_IP:-}" ]; then
    PUBLIC_IP="${PUBLIC_IP}"
else
    PUBLIC_IP=$(curl -s -4 --max-time 5 https://ifconfig.me || curl -s -4 --max-time 5 https://api.ipify.org || echo "127.0.0.1")
fi

echo "Target Host Public IP: ${PUBLIC_IP}"
DOMAIN="${PUBLIC_IP}.sslip.io"

# 2. Ensure namespace exists
echo "Ensuring namespace '${NAMESPACE}' exists..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# 3. Apply the free Kustomize overlay
echo "Applying Kubernetes manifests via Kustomize..."
kubectl apply -k infrastructure/k8s/overlays/free/ -n "${NAMESPACE}"

# 4. Wait for database and redis to be ready
echo "Waiting for PostgreSQL and Redis deployments..."
kubectl rollout status deployment/postgres -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/redis -n "${NAMESPACE}" --timeout=120s

# 5. Wait for API, Web, and Worker deployments
echo "Waiting for API, Web, and Worker deployments..."
kubectl rollout status deployment/airex-api -n "${NAMESPACE}" --timeout=180s
kubectl rollout status deployment/airex-web -n "${NAMESPACE}" --timeout=180s
kubectl rollout status deployment/airex-worker -n "${NAMESPACE}" --timeout=120s

echo "=== Deployment Succeeded! ==="
echo "Web Ingress URL: http://app.${DOMAIN}"
echo "API Ingress URL: http://api.${DOMAIN}/api/v1"
echo "Direct NodePort/Host: http://${PUBLIC_IP}:3000 (Web), http://${PUBLIC_IP}:8000 (API)"
