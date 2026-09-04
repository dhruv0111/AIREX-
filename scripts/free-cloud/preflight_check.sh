#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# AIREX Zero-Cost Cloud Preflight Validation Script
# Verifies host specifications, k3s cluster, storage, and networking
# ==============================================================================

echo "============================================================"
echo "          AIREX Free Cloud Preflight Validation             "
echo "============================================================"

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

report_pass() {
    echo -e "  [PASS] $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

report_warn() {
    echo -e "  [WARN] $1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

report_fail() {
    echo -e "  [FAIL] $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

# 1. Operating System
echo "1. Checking Operating System..."
OS_NAME=$(uname -s 2>/dev/null || echo "Unknown")
if [ "${OS_NAME}" == "Linux" ]; then
    report_pass "Operating System is Linux ($(uname -r))"
else
    report_warn "Operating System is ${OS_NAME} (Linux recommended for k3s)"
fi

# 2. CPU Architecture
echo "2. Checking CPU Architecture..."
ARCH=$(uname -m 2>/dev/null || echo "Unknown")
if [ "${ARCH}" == "aarch64" ] || [ "${ARCH}" == "arm64" ]; then
    report_pass "CPU Architecture is ARM64 / aarch64 (Oracle A1 Flex Shape)"
elif [ "${ARCH}" == "x86_64" ]; then
    report_pass "CPU Architecture is x86_64 (AMD Micro / Standard Shape)"
else
    report_warn "Unrecognized CPU Architecture: ${ARCH}"
fi

# 3. Available Memory (RAM)
echo "3. Checking Available RAM..."
if [ -f /proc/meminfo ]; then
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_MB=$(( TOTAL_RAM_KB / 1024 ))
    if [ "${TOTAL_RAM_MB}" -ge 2048 ]; then
        report_pass "System RAM: ${TOTAL_RAM_MB} MB (Meets 2048 MB requirement)"
    elif [ "${TOTAL_RAM_MB}" -ge 900 ]; then
        report_warn "System RAM: ${TOTAL_RAM_MB} MB (Low memory: ensure 2GB swap is enabled)"
    else
        report_fail "System RAM: ${TOTAL_RAM_MB} MB (Below minimum required memory)"
    fi
else
    report_warn "Unable to read /proc/meminfo"
fi

# 4. Available Disk Space
echo "4. Checking Available Disk Space on Root..."
AVAIL_DISK_GB=$(df -BG / 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo "0")
if [ "${AVAIL_DISK_GB}" -ge 10 ]; then
    report_pass "Free Disk Space: ${AVAIL_DISK_GB} GB (Meets 10 GB requirement)"
elif [ "${AVAIL_DISK_GB}" -ge 5 ]; then
    report_warn "Free Disk Space: ${AVAIL_DISK_GB} GB (Adequate, monitor backup directory)"
else
    report_fail "Free Disk Space: ${AVAIL_DISK_GB} GB (Insufficient space on root filesystem)"
fi

# 5. Check kubectl & k3s
echo "5. Checking Kubernetes / k3s Tooling..."
if command -v kubectl >/dev/null 2>&1; then
    report_pass "kubectl command is available ($(kubectl version --client --short 2>/dev/null || echo 'installed'))"
else
    report_fail "kubectl is not installed. Run 'curl -sfL https://get.k3s.io | sh -'"
fi

# 6. Cluster Reachability
echo "6. Checking Kubernetes Cluster Reachability..."
if kubectl cluster-info >/dev/null 2>&1; then
    report_pass "Connected to active Kubernetes cluster"
    
    # 7. Check Nodes Ready
    NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | grep -c "Ready" || echo "0")
    if [ "${NODE_COUNT}" -ge 1 ]; then
        report_pass "Found ${NODE_COUNT} Ready Kubernetes Node(s)"
    else
        report_fail "No Ready Kubernetes nodes found"
    fi

    # 8. Check Default StorageClass for PVCs
    SC_COUNT=$(kubectl get storageclass --no-headers 2>/dev/null | wc -l || echo "0")
    if [ "${SC_COUNT}" -ge 1 ]; then
        report_pass "Default StorageClass is present for local PersistentVolumeClaims"
    else
        report_warn "No StorageClass found; k3s local-path provisioner recommended"
    fi
else
    report_fail "Cannot connect to Kubernetes cluster. Ensure KUBECONFIG is set: export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
fi

# 9. Inbound Port Availability (80, 443)
echo "7. Checking Port Availability..."
for PORT in 80 443; do
    if command -v ss >/dev/null 2>&1; then
        if ss -tuln | grep -q ":${PORT} "; then
            report_pass "Port ${PORT} is bound (Ingress / Web listener active)"
        else
            report_warn "Port ${PORT} is currently free (Traefik Ingress will bind during deployment)"
        fi
    fi
done

# 10. DNS Resolution Verification
echo "8. Checking Public DNS & Outbound Connectivity..."
if curl -s --max-time 5 https://ifconfig.me >/dev/null 2>&1 || curl -s --max-time 5 https://api.ipify.org >/dev/null 2>&1; then
    PUBLIC_IP=$(curl -s -4 --max-time 5 https://ifconfig.me || curl -s -4 --max-time 5 https://api.ipify.org || echo "")
    if [ -n "${PUBLIC_IP}" ]; then
        report_pass "Public IPv4 detected: ${PUBLIC_IP}"
        report_pass "Wildcard DNS endpoint: app.${PUBLIC_IP}.sslip.io"
    else
        report_warn "Outbound HTTP reachable, but public IP lookup timed out"
    fi
else
    report_warn "Cannot reach public IP discovery endpoint; check VM outbound security list"
fi

echo "============================================================"
echo "Preflight Summary: ${PASS_COUNT} PASSED, ${WARN_COUNT} WARNINGS, ${FAIL_COUNT} FAILURES"
echo "============================================================"

if [ "${FAIL_COUNT}" -gt 0 ]; then
    echo "ERROR: Preflight validation failed. Please address the [FAIL] items above before deploying."
    exit 1
else
    echo "SUCCESS: Host and cluster satisfy all preflight prerequisites!"
    exit 0
fi
