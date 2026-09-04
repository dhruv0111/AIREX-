# AIREX Phase 17.2.1 — Oracle Cloud Free Setup Checklist

This document provides a simple, linear checklist for setting up a $0.00/month cloud deployment of AIREX on Oracle Cloud Always Free.

---

## Reality Status: `REQUIRES USER ACTION`

> [!IMPORTANT]
> **Zero Cost Guarantee:**
> All steps listed below use Oracle Cloud's **Always Free** tier and GitHub's free container registry quota. Do not enter payment information to upgrade to paid architectures or provision paid compute instances.

---

## 27-Point Step-by-Step Checklist

### Section A: Oracle Cloud Account & Infrastructure (Manual User Actions)

- [ ] **Step 1: Create Oracle Cloud Free Tier Account**  
  *Execution:* Web Browser  
  *Action:* Navigate to `https://www.oracle.com/cloud/free/` and complete registration.

- [ ] **Step 2: Complete Account Verification**  
  *Execution:* Web Browser / Email  
  *Action:* Complete email verification and identity verification.

- [ ] **Step 3: Select Home Region with Always Free Capacity**  
  *Execution:* Oracle Cloud Console  
  *Action:* Select a region with high Ampere A1 ARM availability (e.g., `us-ashburn-1`, `us-phoenix-1`, `eu-frankfurt-1`).

- [ ] **Step 4: Provision Always Free ARM Compute Instance**  
  *Execution:* Oracle Cloud Console -> Compute -> Instances -> Create Instance  
  *Configuration:*  
  * Shape: `VM.Standard.A1.Flex` (Ampere ARM)  
  * OCPU: 4 cores (Always Free eligible)  
  * Memory: 24 GB RAM (Always Free eligible)  
  * Boot Volume: 50 GB to 200 GB (Always Free eligible)

- [ ] **Step 5: Select Operating System Image**  
  *Execution:* Oracle Cloud Console  
  *Action:* Choose **Ubuntu 22.04 LTS (aarch64)**.

- [ ] **Step 6: Configure SSH Key Pair**  
  *Execution:* Oracle Cloud Console / Local Terminal  
  *Action:* Generate or upload your public SSH key (`id_rsa.pub` or `id_ed25519.pub`) and save the private key locally.

- [ ] **Step 7: Configure VCN Security List & Firewall**  
  *Execution:* Oracle Cloud Console -> Networking -> Virtual Cloud Networks -> Ingress Rules  
  *Action:* Add Ingress Rules for Ports:  
  * `22` (SSH)  
  * `80` (HTTP Ingress)  
  * `443` (HTTPS Ingress)  
  * `8000` (API Direct NodePort, optional)  
  * `3000` (Web Direct NodePort, optional)

- [ ] **Step 8: Record Real Public IP Address**  
  *Execution:* Oracle Cloud Console -> Instances -> Instance Details  
  *Action:* Copy the Assigned Public IPv4 Address (e.g., `129.153.xx.xx`).

---

### Section B: Remote VM Connection & Tooling (User / SSH Terminal)

- [ ] **Step 9: Connect to the VM via SSH**  
  *Execution:* Local Terminal / Windows PowerShell  
  *Command:* `ssh -i <path_to_private_key> ubuntu@<VM_PUBLIC_IP>`

- [ ] **Step 10: Install Docker, Git & k3s**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:*
  ```bash
  sudo apt-get update && sudo apt-get install -y curl git ufw
  curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
  ```

- [ ] **Step 11: Open OS Firewall (iptables / ufw)**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:*
  ```bash
  sudo iptables -I INPUT -p tcp -m multiport --dports 80,443,3000,8000 -j ACCEPT
  sudo netfilter-persistent save || true
  ```

- [ ] **Step 12: Clone AIREX Repository on VM**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `git clone https://github.com/dhruv0111/AIREX-.git ~/airex && cd ~/airex`

---

### Section C: Registry & Credentials Configuration (User Actions)

- [ ] **Step 13: Configure GitHub Container Registry (GHCR) Access Token**  
  *Execution:* GitHub -> Settings -> Developer Settings -> Personal Access Tokens (Classic) -> `read:packages`  
  *Action:* Generate token with read access to packages.

- [ ] **Step 14: Configure Kubernetes Pull Secret on VM**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:*
  ```bash
  kubectl create namespace airex-free --dry-run=client -o yaml | kubectl apply -f -
  kubectl create secret docker-registry ghcr-secret \
    --docker-server=ghcr.io \
    --docker-username=<GITHUB_USERNAME> \
    --docker-password=<GITHUB_PAT_TOKEN> \
    --docker-email=<YOUR_EMAIL> \
    -n airex-free
  ```

- [ ] **Step 15: Configure Application Secrets**  
  *Execution:* SSH Terminal on Oracle VM  
  *Action:* Edit `infrastructure/k8s/overlays/free/secrets.yaml` with secure random strings:
  ```bash
  sed -i "s/CHANGE_ME_DATABASE_PASSWORD/$(openssl rand -hex 16)/" infrastructure/k8s/overlays/free/secrets.yaml
  sed -i "s/CHANGE_ME_SECRET_KEY/$(openssl rand -hex 32)/" infrastructure/k8s/overlays/free/secrets.yaml
  ```

---

### Section D: Automated Deployment Execution (Scripted Actions)

- [ ] **Step 16: Deploy In-Cluster PostgreSQL 16 & Redis 7**  
  *Execution:* SSH Terminal on Oracle VM  
  *Action:* Executed automatically by deploy script or manually via `kubectl apply -k infrastructure/k8s/overlays/free/`.

- [ ] **Step 17: Deploy AIREX API, Web & Worker Services**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `./scripts/free-cloud/deploy_free_k3s.sh <VM_PUBLIC_IP>`

- [ ] **Step 18: Verify Pod Readiness**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `kubectl get pods -n airex-free` (All pods must show `1/1 Running`).

- [ ] **Step 19: Run Database Migrations**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `./scripts/free-cloud/run_migrations.sh`

- [ ] **Step 20: Verify Wildcard Ingress Resolution (`sslip.io`)**  
  *Execution:* Web Browser / Local Terminal  
  *Action:* Confirm DNS resolution of `http://app.<VM_PUBLIC_IP>.sslip.io` and `http://api.<VM_PUBLIC_IP>.sslip.io`.

- [ ] **Step 21: Verify TLS Certificate (Optional / Production Domain)**  
  *Execution:* Traefik ACME HTTP-01 or Let's Encrypt cert-manager.

---

### Section E: Validation, Disaster Recovery & Maintenance

- [ ] **Step 22: Execute Remote Smoke Test Suite**  
  *Execution:* Local Terminal or SSH on Oracle VM  
  *Command:* `./scripts/free-cloud/smoke_test.sh http://api.<VM_PUBLIC_IP>.sslip.io`

- [ ] **Step 23: Test Web UI Access**  
  *Execution:* Web Browser  
  *Action:* Access `http://app.<VM_PUBLIC_IP>.sslip.io/login` and verify UI renders.

- [ ] **Step 24: Test User Registration & Login in Browser**  
  *Execution:* Web Browser  
  *Action:* Register new user, confirm redirect to `/dashboard`.

- [ ] **Step 25: Execute Database Backup**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `./scripts/free-cloud/backup_db.sh`

- [ ] **Step 26: Execute Non-Destructive Restore Test**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `./scripts/free-cloud/restore_db.sh`

- [ ] **Step 27: Setup Daily Cron Backup Job**  
  *Execution:* SSH Terminal on Oracle VM  
  *Command:* `(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/airex/scripts/free-cloud/backup_db.sh") | crontab -`

---

## Summary of Execution Roles

| Stage | Responsible Actor | Environment |
| :--- | :--- | :--- |
| **Account & VM Creation (Steps 1–8)** | User | Oracle Cloud Web Console |
| **Connection & OS Setup (Steps 9–12)** | User | Local Terminal -> SSH -> Oracle VM |
| **Secret & Token Configuration (Steps 13–15)** | User | SSH Terminal on Oracle VM |
| **Deployment & Migrations (Steps 16–21)** | Script (`deploy_free_k3s.sh`) | SSH Terminal on Oracle VM |
| **Smoke & Verification (Steps 22–24)** | Script & User | Local Browser / Terminal |
| **DR & Maintenance (Steps 25–27)** | Script (`backup_db.sh`) | SSH Terminal on Oracle VM |
