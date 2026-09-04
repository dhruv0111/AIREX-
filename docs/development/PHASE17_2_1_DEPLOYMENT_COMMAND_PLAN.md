# AIREX Phase 17.2.1 — Deployment Command Plan

This document defines the exact command sequences for deploying AIREX to Oracle Cloud Always Free.

---

## 1. Parameter & Placeholder Reference

| Parameter Name | Placeholder Value | Description |
| :--- | :--- | :--- |
| **VM Public IPv4** | `<VM_PUBLIC_IP>` | Real public IP allocated by Oracle Cloud (e.g. `129.153.45.67`) |
| **SSH Username** | `<SSH_USER>` | Default OS user (`ubuntu` for Ubuntu images) |
| **SSH Private Key** | `<PATH_TO_PRIVATE_KEY>` | Path to your SSH key file on your local machine (e.g. `~/.ssh/oracle_key`) |
| **GHCR Username** | `<GHCR_USERNAME>` | Your GitHub account handle |
| **GHCR Personal Token** | `<GHCR_PAT_TOKEN>` | GitHub PAT with `read:packages` (or `write:packages`) scope |
| **Image Tag** | `<IMAGE_TAG>` | Immutable build tag (e.g. `v1.0.0-$(git rev-parse --short HEAD)` or `latest`) |
| **Database Password** | `<DATABASE_PASSWORD>` | Randomly generated 32-character hex database secret |
| **Application Secret** | `<APPLICATION_SECRET_KEY>` | Randomly generated 64-character hex secret key for JWT session hashing |
| **Public Hostname (Web)** | `app.<VM_PUBLIC_IP>.sslip.io` | Dynamically resolved web domain |
| **Public Hostname (API)** | `api.<VM_PUBLIC_IP>.sslip.io` | Dynamically resolved API domain |

---

## 2. Command Sequence A: Local Machine Actions

*Environment: Windows PowerShell / Local Terminal*

### 2.1 Multi-Arch Image Build & Push (Optional if using CI/CD)
```bash
# [LOCAL TERMINAL]
export REGISTRY="ghcr.io/<GHCR_USERNAME>"
export VERSION_TAG="<IMAGE_TAG>"
export PUSH_FLAG="--push"

# Build & Push multi-arch Docker images to GHCR
./scripts/free-cloud/build_multiarch.sh
```

### 2.2 SSH Connect to Remote VM
```bash
# [LOCAL TERMINAL]
ssh -i "<PATH_TO_PRIVATE_KEY>" <SSH_USER>@<VM_PUBLIC_IP>
```

---

## 3. Command Sequence B: Remote Oracle VM Initialization

*Environment: SSH Terminal on Oracle VM (`ubuntu@<VM_PUBLIC_IP>`)*

### 3.1 OS Packages & Host Firewall
```bash
# [SSH TERMINAL ON VM]
sudo apt-get update && sudo apt-get install -y curl git iptables-persistent

# Open Ingress Ports 80, 443, 3000, 8000
sudo iptables -I INPUT 6 -m state --state NEW -p tcp -m multiport --dports 80,443,3000,8000 -j ACCEPT
sudo netfilter-persistent save
```

### 3.2 Single-Node k3s Cluster Setup
```bash
# [SSH TERMINAL ON VM]
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> ~/.bashrc

# Verify node is ready
kubectl get nodes -o wide
```

### 3.3 Clone Repository
```bash
# [SSH TERMINAL ON VM]
git clone https://github.com/dhruv0111/AIREX-.git ~/airex
cd ~/airex
```

### 3.4 Secret Generation & Namespace Provisioning
```bash
# [SSH TERMINAL ON VM]
kubectl create namespace airex-free --dry-run=client -o yaml | kubectl apply -f -

# Generate random secure credentials
DB_PASS=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)

sed -i "s/CHANGE_ME_DATABASE_PASSWORD/${DB_PASS}/" infrastructure/k8s/overlays/free/secrets.yaml
sed -i "s/CHANGE_ME_SECRET_KEY/${SECRET_KEY}/" infrastructure/k8s/overlays/free/secrets.yaml

# (Optional) GHCR Pull Secret
# kubectl create secret docker-registry ghcr-secret \
#   --docker-server=ghcr.io \
#   --docker-username=<GHCR_USERNAME> \
#   --docker-password=<GHCR_PAT_TOKEN> \
#   --docker-email=<YOUR_EMAIL> \
#   -n airex-free
```

---

## 4. Command Sequence C: Stack Deployment & Migrations

*Environment: SSH Terminal on Oracle VM (`ubuntu@<VM_PUBLIC_IP>`)*

### 4.1 Launch Microservices Stack
```bash
# [SSH TERMINAL ON VM]
chmod +x scripts/free-cloud/*.sh
./scripts/free-cloud/deploy_free_k3s.sh <VM_PUBLIC_IP>
```

### 4.2 Execute Database Migrations
```bash
# [SSH TERMINAL ON VM]
./scripts/free-cloud/run_migrations.sh
```

### 4.3 Verify Cluster Health & Pod Status
```bash
# [SSH TERMINAL ON VM]
kubectl get pods,svc,ingress,pvc -n airex-free
```

---

## 5. Command Sequence D: Remote Validation & Smoke Testing

*Environment: Local Terminal or SSH Terminal*

### 5.1 Execute Automated Smoke Probes
```bash
# [LOCAL OR SSH TERMINAL]
./scripts/free-cloud/smoke_test.sh http://api.<VM_PUBLIC_IP>.sslip.io
```

### 5.2 Direct Host Health Checks (cURL)
```bash
# Health Live Probe
curl -i http://api.<VM_PUBLIC_IP>.sslip.io/health/live

# Health Ready Probe
curl -i http://api.<VM_PUBLIC_IP>.sslip.io/health/ready

# OpenAPI Documentation
curl -i http://api.<VM_PUBLIC_IP>.sslip.io/openapi.json
```

---

## 6. Command Sequence E: Disaster Recovery & Rollback

*Environment: SSH Terminal on Oracle VM (`ubuntu@<VM_PUBLIC_IP>`)*

### 6.1 Trigger Database Backup
```bash
# [SSH TERMINAL ON VM]
./scripts/free-cloud/backup_db.sh
```

### 6.2 Test Database Integrity Restore
```bash
# [SSH TERMINAL ON VM]
./scripts/free-cloud/restore_db.sh
```

### 6.3 Fast Application Rollback
```bash
# [SSH TERMINAL ON VM]
./scripts/free-cloud/rollback.sh
```

### 6.4 Clean Teardown (Destructive)
```bash
# [SSH TERMINAL ON VM]
./scripts/free-cloud/destroy.sh
```
