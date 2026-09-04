# AIREX — PHASE 17.2: CURRENT ARCHITECTURE & DEPENDENCY AUDIT
## Zero-Cost Transition & Dependency Analysis

**Date:** September 4, 2026  
**Auditor:** Antigravity Advanced Agentic Engineering  
**Scope:** Architecture Analysis for Transitioning from Paid Cloud Assumptions to Zero-Cost Always Free Hosting

---

## 1. MANDATORY PLATFORM COMPONENTS

The AIREX reliability platform requires the following core components to operate fully:

1. **FastAPI Backend (`apps/api`):** REST API handling all 17 platform domains (Auth, Projects, Datasets, Evaluations, Experiments, Generations, Models, Observability, Providers, Rubrics, Alerts, CI, Intelligence, Enterprise SSO, Compliance, Operations SRE).
2. **Next.js Web Frontend (`apps/web`):** React 19 / Next.js 15 standalone server providing the user interface and SRE operations console.
3. **Background Task Worker (`app.workers.worker`):** In-process or standalone worker dequeuing asynchronous evaluation, benchmark, and retention tasks.
4. **PostgreSQL Relational Database:** Persistent storage for users, organizations, projects, test runs, and canonical compliance evidence.
5. **Redis In-Memory Cache & Message Broker:** Task queue state, distributed rate limiting, and cache layer.
6. **Reverse Proxy & Ingress:** Routing external HTTP traffic to `/api/v1` (API) and `/` (Web) with TLS termination.
7. **Persistent File Storage:** Local storage mounted at `/app/data` for backups, logs, and temporary evaluation fixtures.

---

## 2. AUDIT OF CURRENT PAID CLOUD ASSUMPTIONS & FREE REPLACEMENTS

| Architectural Area | Previous Enterprise/Paid Assumption | Zero-Cost Free Cloud Replacement | Impact / Compatibility |
| :--- | :--- | :--- | :--- |
| **Compute / Orchestration** | AWS EKS Multi-Node Cluster ($73+/mo + node costs) | Single-node **k3s** on Oracle Always Free ARM (4 OCPU, 24GB RAM) or Docker Compose | **100% Compatible.** Single-node has no multi-AZ redundancy but runs all pods effortlessly. |
| **Database Engine** | AWS Aurora Serverless / Managed RDS ($50+/mo) | **In-Cluster PostgreSQL 16** with persistent volume claim (PVC) on local NVMe/SSD block volume | **100% Compatible.** Native PostgreSQL protocol; local automated `pg_dump` backups replace RDS automated snapshots. |
| **Redis Cache / Queue** | AWS ElastiCache Redis ($30+/mo) | **In-Cluster Redis 7** container with Append-Only File (AOF) persistence volume | **100% Compatible.** Standard Redis protocol matching `RedisTaskQueue`. |
| **Container Registry** | AWS ECR ($0.10/GB storage + transfer) | **GitHub Container Registry (`ghcr.io`)** (Free for public, 500MB free private) | **100% Compatible.** Standard OCI container registry. |
| **DNS Resolution** | AWS Route 53 ($0.50/zone + queries) | **Free IP Wildcard DNS (`sslip.io` or `nip.io`)** or DuckDNS / Cloudflare Free | **100% Compatible.** Zero domain registration or DNS hosting cost. |
| **TLS / HTTPS Certificates**| AWS Certificate Manager (ACM) | **Let's Encrypt** via `cert-manager` HTTP-01 challenge | **100% Compatible.** Automated 90-day renewable SSL certificates. |
| **CI/CD Pipeline** | Paid GitHub Runners / AWS CodeBuild | **GitHub Actions Free Tier** (2,000 free runner minutes/month) | **100% Compatible.** Multi-arch `docker/buildx` builds execute within free quota. |
| **Object Storage** | AWS S3 ($0.023/GB) | **Local Persistent Storage Mounts** or Oracle Cloud Always Free Object Storage (20GB free) | **100% Compatible.** AIREX uses filesystem abstraction for backups and local data. |

---

## 3. IDENTIFIED RESOURCE CONSUMPTION ESTIMATES (FREE ENVIRONMENT)

| Service Pod / Container | CPU Request | CPU Limit | Memory Request | Memory Limit | Storage Requirement |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **PostgreSQL 16** | 100m | 500m | 256Mi | 1024Mi | 10 GiB PVC |
| **Redis 7 (AOF)** | 50m | 250m | 128Mi | 512Mi | 2 GiB PVC |
| **AIREX API (1-2 replicas)**| 150m | 500m | 256Mi | 512Mi | 2 GiB (Ephemeral) |
| **AIREX Web (1 replica)** | 100m | 300m | 128Mi | 384Mi | 1 GiB (Ephemeral) |
| **AIREX Worker (1 replica)**| 100m | 500m | 256Mi | 512Mi | 5 GiB PVC (Backups) |
| **Traefik / Ingress-Nginx**| 50m | 200m | 64Mi | 128Mi | N/A |
| **TOTALS (Combined Stack)**| **~550m** | **~2250m** | **~1.1 GiB** | **~3.0 GiB** | **~20 GiB Block Volume** |

**Hardware Fit Assessment:**
On an Oracle Cloud Always Free ARM Ampere A1 instance (4 OCPU, 24 GB RAM, 200 GB Storage), the entire AIREX stack consumes less than **15% of available RAM** and **15% of available CPU**, leaving ample headroom for smooth operation, database indexing, and evaluation workloads at **$0.00 total monthly cost**.
