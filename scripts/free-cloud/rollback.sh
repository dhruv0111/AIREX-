#!/usr/bin/env bash
set -euo pipefail

# AIREX — Fast Emergency Rollback
NAMESPACE="airex-free"

echo "=== Rolling Back AIREX Deployments in ${NAMESPACE} ==="

kubectl rollout undo deployment/airex-api -n "${NAMESPACE}"
kubectl rollout undo deployment/airex-web -n "${NAMESPACE}"
kubectl rollout undo deployment/airex-worker -n "${NAMESPACE}"

kubectl rollout status deployment/airex-api -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/airex-web -n "${NAMESPACE}" --timeout=120s

echo "=== Rollback Succeeded! ==="
