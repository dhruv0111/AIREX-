# AIREX Phase 17.2.2 — Oracle VM Deployment Runbook

**Runbook Target:** Oracle Cloud Always Free (`VM.Standard.A1.Flex` ARM64 / Ubuntu 22.04)  
**Total Estimated Cost:** **$0.00 / month**  
**Execution Type:** Semi-Automated (User infrastructure initialization + Scripted cluster rollout)

---

## 1. Prerequisites & Preparation Checklist

Before executing this runbook, ensure you have:
1. **Oracle Cloud Free Tier Account** ([oracle.com/cloud/free](https://www.oracle.com/cloud/free/)).
2. **Local SSH Client** (Windows PowerShell `OpenSSH`, Terminal, or PuTTY).
3. **Public/Private SSH Key Pair** (`~/.ssh/id_rsa` or `~/.ssh/id_ed25519`).
4. **Git** installed locally or on the target instance.

---

## 2. PART A — COMMANDS RUN ON USER'S LOCAL COMPUTER

*Execute the following commands in your local terminal or Windows PowerShell.*

### A.1 Generate SSH Key (If you don't already have one)
```powershell
# [LOCAL WINDOWS POWERSHELL / TERMINAL]
ssh-keygen -t ed25519 -f "$HOME/.ssh/oracle_free_key" -C "airex-free-cloud"
# Note: Keep oracle_free_key private; you will paste oracle_free_key.pub into Oracle Console.
```

### A.2 (Optional) Build and Push Multi-Arch Docker Images via Local Buildx
*Note: If you are building images directly on the remote VM, you may skip this step.*
```bash
# [LOCAL TERMINAL]
export REGISTRY="ghcr.io/<YOUR_GITHUB_USERNAME>"
export VERSION_TAG="latest"
export PUSH_FLAG="--push"

./scripts/free-cloud/build_multiarch.sh
```

### A.3 Connect to the Remote Oracle VM via SSH
Once your instance is in the `RUNNING` state in Oracle Cloud Console and you have its public IP:
```powershell
# [LOCAL WINDOWS POWERSHELL / TERMINAL]
# Replace <PATH_TO_KEY> with $HOME\.ssh\oracle_free_key and <VM_PUBLIC_IP> with your real IP (e.g. 129.153.45.67)
ssh -i "$HOME/.ssh/oracle_free_key" ubuntu@<VM_PUBLIC_IP>
```

### A.4 Remote Smoke Verification from Local Computer
*Run this after Part B is complete:*
```powershell
# [LOCAL WINDOWS POWERSHELL / TERMINAL]
# Run automated 20-point HTTP probe against the remote VM's wildcard domain:
curl -i http://api.<VM_PUBLIC_IP>.sslip.io/health/live
curl -i http://api.<VM_PUBLIC_IP>.sslip.io/health/ready
```

---

## 3. PART B — COMMANDS RUN INSIDE THE ORACLE VM

*Execute the following commands in your SSH terminal connected to `ubuntu@<VM_PUBLIC_IP>`.*

### B.1 Step 1: Host System Update & Firewall Configuration
```bash
# [SSH TERMINAL ON ORACLE VM]
sudo apt-get update && sudo apt-get install -y curl git iptables-persistent

# Open inbound traffic for HTTP (80), HTTPS (443), Web (3000), API (8000), and k3s API (6443)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp -m multiport --dports 80,443,3000,8000,6443 -j ACCEPT
sudo netfilter-persistent save
```

### B.2 Step 2: Install k3s Lightweight Kubernetes
```bash
# [SSH TERMINAL ON ORACLE VM]
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> ~/.bashrc

# Confirm single-node k3s cluster is Active
kubectl get nodes -o wide
```

### B.3 Step 3: Clone AIREX Repository on VM
```bash
# [SSH TERMINAL ON ORACLE VM]
git clone https://github.com/dhruv0111/AIREX-.git ~/airex
cd ~/airex
chmod +x scripts/free-cloud/*.sh
```

### B.4 Step 4: Run Preflight Validation Check
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/preflight_check.sh
```
*Expected Output: All checks report `[PASS]` for Linux OS, ARM64 architecture, memory, disk, and k3s reachability.*

### B.5 Step 5: Configure Application Secrets
```bash
# [SSH TERMINAL ON ORACLE VM]
# Generate random cryptographic credentials into the Kubernetes secret template
DB_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)
FERNET_KEY=$(openssl rand -base64 32)

sed -i "s/CHANGE_ME_DATABASE_PASSWORD/${DB_PASSWORD}/" infrastructure/k8s/overlays/free/secrets.yaml
sed -i "s/CHANGE_ME_SECRET_KEY/${JWT_SECRET}/" infrastructure/k8s/overlays/free/secrets.yaml
```

### B.6 Step 6: Deploy AIREX Microservices Stack
```bash
# [SSH TERMINAL ON ORACLE VM]
# Detects host public IP automatically and configures wildcard sslip.io ingress
./scripts/free-cloud/deploy_free_k3s.sh
```
*Expected Output: Rollouts for `postgres`, `redis`, `airex-api`, `airex-web`, and `airex-worker` succeed with zero errors.*

### B.7 Step 7: Apply Alembic Database Migrations
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/run_migrations.sh
```
*Expected Output: Database schemas and tables are created inside the in-cluster PostgreSQL instance.*

### B.8 Step 8: Verify Deployment Status
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/status.sh
```

### B.9 Step 9: Execute Automated 20-Point Smoke Tests
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/smoke_test.sh http://api.$(curl -s -4 https://ifconfig.me).sslip.io
```

---

## 4. PART C — DISASTER RECOVERY & DAY-2 OPERATIONS

*Commands run on the Oracle VM as needed.*

### C.1 Database Backup
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/backup_db.sh
```
*Creates a streaming `pg_dump.sql.gz` in `/var/airex/backups/` with a corresponding `.sha256` checksum.*

### C.2 Non-Destructive Restore Test
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/restore_db.sh
```
*Validates checksum integrity and restores into test database `airex_restore_test` to verify table counts without disturbing live data.*

### C.3 Emergency Rollback
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/rollback.sh
```

### C.4 Clean Teardown
```bash
# [SSH TERMINAL ON ORACLE VM]
./scripts/free-cloud/destroy.sh
```

---

## 5. Troubleshooting Matrix

| Symptom | Probable Cause | Remediation Command |
| :--- | :--- | :--- |
| **Connection timed out on SSH** | Oracle VCN Security List missing port 22 | Add Ingress Rule for Port 22 CIDR `0.0.0.0/0` in Oracle Cloud Console |
| **Ingress returns 502 Bad Gateway** | API or Web pod still starting | Run `kubectl get pods -n airex-free` and wait for `Running` status |
| **HTTP connections refused on port 80** | VM Ubuntu iptables blocking port | Run `sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT` |
| **Database migration fails** | PostgreSQL pod not fully initialized | Verify with `./scripts/free-cloud/status.sh` and re-run `./scripts/free-cloud/run_migrations.sh` |
| **Low RAM on AMD 1GB Micro VM** | Swap not configured | Run `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
