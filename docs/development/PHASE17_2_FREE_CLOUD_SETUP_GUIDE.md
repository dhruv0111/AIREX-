# AIREX — PHASE 17.2: ZERO-COST FREE CLOUD SETUP GUIDE
## Step-by-Step Deployment on Oracle Cloud Always Free + k3s

**Total Cost:** **$0.00 / month**  
**Required Cloud Tier:** Oracle Cloud Always Free (`VM.Standard.A1.Flex` ARM64 or `VM.Standard.E2.1.Micro` AMD)  
**Estimated Setup Time:** 15–20 minutes

---

> [!WARNING]
> **BILLING SAFETY & ZERO-COST GUARANTEE:**
> Oracle Cloud provides **Always Free** resources that remain free forever.
> - **DO NOT** click "Upgrade to Paid Account" or enable paid services.
> - Stick strictly to the `VM.Standard.A1.Flex` shape (up to 4 OCPU, 24 GB RAM, 200 GB Storage) or `VM.Standard.E2.1.Micro` (1 OCPU, 1 GB RAM).
> - All DNS is provided free via `sslip.io` wildcard DNS. **DO NOT** purchase a custom domain unless desired.

---

## EXECUTION CONTEXT REFERENCE
Every step in this guide is categorized into either:
* 👤 **USER ACTION**: Manual task performed by the user in a browser or local terminal.
* 🤖 **SCRIPT / AUTOMATED ACTION**: Automated operation executed via provided shell scripts.

And tagged with its execution location:
* `[LOCAL BROWSER]`
* `[LOCAL TERMINAL / WINDOWS POWERSHELL]`
* `[SSH TERMINAL INSIDE ORACLE VM]`

---

## PART 1: INFRASTRUCTURE PROVISIONING (USER ACTIONS)

### Step 1: Create Oracle Cloud Always Free Account 👤 `[LOCAL BROWSER]`
1. Navigate to [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) and click **Start for free**.
2. Select your closest **Home Region** (note: Always Free compute is anchored to your home region).
3. Complete registration and email verification.

### Step 2: Provision Always Free ARM VM Instance 👤 `[LOCAL BROWSER]`
1. In the Oracle Cloud Console, navigate to **Compute > Instances > Create Instance**.
2. **Name:** `airex-free-node`
3. **Image:** Ubuntu 22.04 LTS (`aarch64`).
4. **Shape:** Click **Change Shape** -> **Ampere (ARM-based Processor)** -> `VM.Standard.A1.Flex`.
   - **OCPUs:** `4`
   - **Memory:** `24 GB`
   *(If ARM is temporarily out of capacity in your region, choose `VM.Standard.E2.1.Micro` AMD with 1 OCPU and 1 GB RAM).*
5. **Networking:** Select default VCN and public subnet; ensure **Assign a public IPv4 address** is checked.
6. **SSH Keys:** Save the private key (`id_rsa` or `id_ed25519`) to your local machine and upload the corresponding public key.
7. Click **Create** and wait ~60 seconds for the instance status to show `RUNNING`.
8. Copy your instance **Public IPv4 Address** (e.g. `129.153.45.67`).

### Step 3: Configure VCN Firewall Rules 👤 `[LOCAL BROWSER]`
1. On the instance details page, click on the **Subnet** link -> **Default Security List for VCN**.
2. Click **Add Ingress Rules** and add the following rules for CIDR `0.0.0.0/0`:
   - **Port 80 (HTTP Ingress):** Destination Port `80` (TCP)
   - **Port 443 (HTTPS Ingress):** Destination Port `443` (TCP)
   - **Port 3000 (Web Direct Port):** Destination Port `3000` (TCP, optional)
   - **Port 8000 (API Direct Port):** Destination Port `8000` (TCP, optional)
3. Click **Add Ingress Rules**.

---

## PART 2: REMOTE VM CONNECTION & PREPARATION (USER & SCRIPT)

### Step 4: SSH into Oracle VM 👤 `[LOCAL TERMINAL / WINDOWS POWERSHELL]`
Run the SSH connection command from your local machine:
```bash
ssh -i /path/to/private_key ubuntu@<YOUR_VM_PUBLIC_IP>
```

### Step 5: Open Host Firewall (iptables) 👤 `[SSH TERMINAL INSIDE ORACLE VM]`
Oracle Cloud Ubuntu images include default iptables firewall rules. Open ports on the host:
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp -m multiport --dports 80,443,3000,8000 -j ACCEPT
sudo apt-get update && sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

### Step 6: Install k3s Lightweight Kubernetes 🤖 `[SSH TERMINAL INSIDE ORACLE VM]`
Install k3s with the embedded Traefik ingress controller:
```bash
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo "export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >> ~/.bashrc

# Verify k3s single-node cluster is active:
kubectl get nodes
```

### Step 7: Clone AIREX Repository on VM 👤 `[SSH TERMINAL INSIDE ORACLE VM]`
```bash
git clone https://github.com/dhruv0111/AIREX-.git ~/airex
cd ~/airex
```

### Step 8: Configure Secrets & Registry Credentials 👤 `[SSH TERMINAL INSIDE ORACLE VM]`
1. Create the `airex-free` namespace:
   ```bash
   kubectl create namespace airex-free --dry-run=client -o yaml | kubectl apply -f -
   ```
2. *(Optional if pulling private images)* Create GitHub Container Registry Secret:
   ```bash
   kubectl create secret docker-registry ghcr-secret \
     --docker-server=ghcr.io \
     --docker-username=<GITHUB_USERNAME> \
     --docker-password=<GITHUB_PAT_TOKEN> \
     --docker-email=<YOUR_EMAIL> \
     -n airex-free
   ```
3. Generate secure cryptographic secrets for database and JWT auth:
   ```bash
   sed -i "s/CHANGE_ME_DATABASE_PASSWORD/$(openssl rand -hex 16)/" infrastructure/k8s/overlays/free/secrets.yaml
   sed -i "s/CHANGE_ME_SECRET_KEY/$(openssl rand -hex 32)/" infrastructure/k8s/overlays/free/secrets.yaml
   ```

---

## PART 3: APPLICATION DEPLOYMENT (SCRIPTED)

### Step 9: Deploy AIREX Microservices Stack 🤖 `[SSH TERMINAL INSIDE ORACLE VM]`
Execute the automated deployment script with your VM's public IP:
```bash
chmod +x scripts/free-cloud/*.sh
./scripts/free-cloud/deploy_free_k3s.sh <YOUR_VM_PUBLIC_IP>
```
*The script deploys in-cluster PostgreSQL 16 (10Gi PVC), Redis 7 (2Gi PVC), API, Web, Worker, and configures Traefik Ingress for `app.<YOUR_VM_PUBLIC_IP>.sslip.io` and `api.<YOUR_VM_PUBLIC_IP>.sslip.io`.*

### Step 10: Run Database Migrations 🤖 `[SSH TERMINAL INSIDE ORACLE VM]`
Execute Alembic database migrations inside the active API pod:
```bash
./scripts/free-cloud/run_migrations.sh
```

---

## PART 4: VERIFICATION & SMOKE TESTING (USER & SCRIPT)

### Step 11: Execute Automated Remote Smoke Tests 🤖 `[LOCAL TERMINAL OR SSH TERMINAL]`
Run the 13-point automated HTTP smoke test suite:
```bash
./scripts/free-cloud/smoke_test.sh http://api.<YOUR_VM_PUBLIC_IP>.sslip.io
```

### Step 12: Verify User Registration & Web UI 👤 `[LOCAL BROWSER]`
1. Open your browser and navigate to: `http://app.<YOUR_VM_PUBLIC_IP>.sslip.io/register`
2. Register a test admin account.
3. Confirm successful login and navigation to `http://app.<YOUR_VM_PUBLIC_IP>.sslip.io/dashboard`.

---

## PART 5: DISASTER RECOVERY & MAINTENANCE (SCRIPTED)

### Step 13: Execute Database Backup 🤖 `[SSH TERMINAL INSIDE ORACLE VM]`
```bash
./scripts/free-cloud/backup_db.sh
```

### Step 14: Execute Non-Destructive Restore Test 🤖 `[SSH TERMINAL INSIDE ORACLE VM]`
```bash
./scripts/free-cloud/restore_db.sh
```

### Step 15: Schedule Daily Automated Backups 🤖 `[SSH TERMINAL INSIDE ORACLE VM]`
```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/airex/scripts/free-cloud/backup_db.sh >> /var/log/airex_backup.log 2>&1") | crontab -
```
