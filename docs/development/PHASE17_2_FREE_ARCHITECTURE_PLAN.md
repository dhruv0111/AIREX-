# AIREX — PHASE 17.2: ZERO-COST FREE ARCHITECTURE PLAN
## Deployment Architecture for Oracle Always Free & Single-Node k3s

**Document Version:** 1.0.0  
**Target Platform:** Oracle Cloud Always Free ARM Ampere A1 (or AMD micro VM) + k3s / Docker Compose Fallback  
**Monthly Cost:** **$0.00 / month (100% Free Tier)**

---

## 1. ARCHITECTURE TOPOLOGY

```
+---------------------------------------------------------------------------------------------------+
| ORACLE CLOUD ALWAYS FREE VM (4 OCPU ARM Ampere A1 / 24 GB RAM / 200 GB Storage / Public IP)       |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | K3S LIGHTWEIGHT KUBERNETES RUNTIME (Single-Node Node / Embedded SQLite Control Plane)       |  |
|  |                                                                                             |  |
|  |  [ Ingress Controller (Traefik / Nginx Ingress) ] <---> Let's Encrypt TLS (cert-manager)   |  |
|  |    |                     |                                                                  |  |
|  |    | (app.*.sslip.io)    | (api.*.sslip.io)                                                 |  |
|  |    v                     v                                                                  |  |
|  |  +----------------+   +-------------------+   +--------------------+                        |  |
|  |  | airex-web      |   | airex-api         |   | airex-worker       |                        |  |
|  |  | (Next.js 15)   |   | (FastAPI Core)    |   | (Task Fleet)       |                        |  |
|  |  +----------------+   +-------------------+   +--------------------+                        |  |
|  |          |                      |                       |                                   |  |
|  |          +----------------------+-----------------------+                                   |  |
|  |                                 |                                                           |  |
|  |         +-----------------------+-----------------------+                                   |  |
|  |         v                                               v                                   |  |
|  |  +--------------------------------+          +------------------------------------+         |  |
|  |  | PostgreSQL 16 Stateful Pod     |          | Redis 7 Persistent Pod             |         |  |
|  |  | (pvc-postgres-data: 10 GiB)   |          | (pvc-redis-data: 2 GiB)            |         |  |
|  |  +--------------------------------+          +------------------------------------+         |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                                                                                   |
|  Host Cron / Automation: Local Daily pg_dump Backups -> /var/airex/backups (SHA-256 Verified)     |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. FREE SERVICE SELECTION & SPECIFICATIONS

| Component | Free Technology Chosen | Free Tier Limits | Replacement Details |
| :--- | :--- | :--- | :--- |
| **Compute VM** | Oracle Cloud VM.Standard.A1.Flex (ARM) | Up to 4 OCPU, 24 GB RAM, 200 GB Storage free forever | Self-hosted single-node Kubernetes (k3s) replaces paid cloud managed clusters. |
| **Kubernetes** | **k3s** by Rancher (v1.30+) | Open source, zero cost | Embedded SQLite control plane, low memory footprint (~512MB RAM). |
| **Database** | Self-hosted **PostgreSQL 16** | Consumes ~500MB RAM, 10GB disk | In-cluster StatefulSet with Local PV replaces AWS Aurora RDS. |
| **Cache & Queue** | Self-hosted **Redis 7** (AOF) | Consumes ~128MB RAM, 2GB disk | In-cluster Deployment with Persistent Volume replaces AWS ElastiCache. |
| **Registry** | **GitHub Container Registry (`ghcr.io`)** | Free for public repositories; 500MB private | Multi-arch images pushed via GitHub Actions; replaces AWS ECR. |
| **DNS Resolution**| **`sslip.io` / `nip.io` Wildcard DNS** | Unlimited, 100% free forever | IP-to-domain mapping (e.g. `123.45.67.89.sslip.io`) requires zero paid domain. |
| **SSL / TLS** | **Let's Encrypt** via ACME / cert-manager | Free automated 90-day certificates | Automated TLS issuance for `*.sslip.io` hostnames. |

---

## 3. REALITY & ARCHITECTURAL LIMITATIONS

To maintain strict truth in advertising, the following realities apply to the zero-cost architecture:

1. **Single-Node Single Point of Failure (SPOF):** Because the free tier provides one compute VM, host hardware failure or VM reboot will result in temporary application downtime.
2. **Local Volume Backup Strategy:** Database backups are stored on local block storage (`/var/airex/backups`) and can be synced to Oracle Always Free Object Storage (20 GB free) via `rclone` or S3 API.
3. **No Horizontal Multi-Node Scaling:** HPA scales pods locally within the single node's CPU/RAM envelope (up to 24 GB RAM on ARM).
4. **No Managed Database Auto-Scaling:** Database storage expansion must be handled by resizing the local PVC.
