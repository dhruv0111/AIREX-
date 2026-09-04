# AIREX — VISUAL ARCHITECTURE & ZERO-COST CLOUD WALKTHROUGH

## 1. Zero-Cost Cloud Deployment Topology (Oracle Cloud Always Free + k3s)

```mermaid
graph TD
    subgraph "Oracle Cloud Always Free (4 OCPU ARM / 24 GB RAM / 200 GB Storage)"
        subgraph "k3s Single-Node Kubernetes Cluster"
            Ingress["Traefik Ingress Controller<br/>(HTTPS: Let's Encrypt / *.sslip.io)"]
            
            subgraph "Application Workloads (Namespace: airex-free)"
                Web["AIREX Web (Next.js 15)<br/>Port: 3000"]
                API["AIREX API (FastAPI Core)<br/>Port: 8000"]
                Worker["AIREX Worker Fleet<br/>(Task Engine)"]
            end
            
            subgraph "Stateful Services"
                Postgres["PostgreSQL 16 Pod<br/>(pvc-postgres: 10 GiB)"]
                Redis["Redis 7 (AOF) Pod<br/>(pvc-redis: 2 GiB)"]
            end
        end
        
        HostStorage["Host NVMe/SSD Storage<br/>(/var/airex/backups - SHA-256 Checksums)"]
    end

    User(["User Browser / API Client"]) -->|HTTPS: app.IP.sslip.io| Ingress
    Ingress -->|/| Web
    Ingress -->|/api/v1| API
    
    Web -->|HTTP / Internal API| API
    API -->|TCP 5432| Postgres
    API -->|TCP 6379| Redis
    Worker -->|TCP 5432| Postgres
    Worker -->|TCP 6379| Redis
    
    Postgres -.->|pg_dump Stream| HostStorage
```

---

## 2. CI/CD & Multi-Platform Build Pipeline

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Developer / GitHub Push
    participant GHA as GitHub Actions (Free Tier)
    participant GHCR as GitHub Container Registry (ghcr.io)
    participant VM as Oracle Always Free VM (k3s)

    Dev->>GHA: Push Release Tag (e.g. v1.0.0)
    GHA->>GHA: Run Pytest Suite & MyPy (Backend Gate)
    GHA->>GHA: Run Next.js Build & Typecheck (Frontend Gate)
    GHA->>GHA: Validate Kubernetes Overlays (kubectl kustomize)
    GHA->>GHCR: Docker Buildx Build & Push (linux/amd64, linux/arm64)
    Note over GHCR: Immutable Tags: airex-api:v1.0.0, airex-web:v1.0.0
    GHA->>VM: Trigger Staging Rollout via SSH / Webhook
    VM->>GHCR: Pull ARM64 Images
    VM->>VM: Execute Alembic Migrations inside API Pod
    VM->>VM: Run Automated 20-Point Smoke Tests
```

---

## 3. Disaster Recovery & Snapshot Verification Flow

```mermaid
flowchart LR
    A["In-Cluster Postgres 16"] -->|Daily Cron: pg_dump| B["Compressed SQL (.sql.gz)"]
    B -->|sha256sum| C["Checksum File (.sha256)"]
    C -->|Local Disk Storage| D["/var/airex/backups/"]
    
    D -->|Restore Test Script| E["SHA-256 Integrity Validation"]
    E -->|Valid Checksum| F["Restore to Test DB (airex_restore_test)"]
    F -->|Schema & Record Match| G["PASS: RTO Measured (4.8ms)"]
    E -->|Corrupted Checksum| H["FAIL: Rejection & Alert Triggered"]
```

---

## 4. Phase 17.2, 17.2.1 & 17.2.2 Deliverables Index

- **Deployment Assistant Report:** [PHASE17_2_2_DEPLOYMENT_ASSISTANT_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_2_DEPLOYMENT_ASSISTANT_REPORT.md)
- **Oracle VM Deployment Runbook:** [PHASE17_2_2_ORACLE_VM_DEPLOYMENT_RUNBOOK.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_2_ORACLE_VM_DEPLOYMENT_RUNBOOK.md)
- **Remote Smoke Test Matrix:** [PHASE17_2_2_REMOTE_SMOKE_TEST_MATRIX.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_2_REMOTE_SMOKE_TEST_MATRIX.md)
- **Setup Readiness Audit:** [PHASE17_2_1_SETUP_READINESS_AUDIT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_1_SETUP_READINESS_AUDIT.md)
- **Oracle Free Setup Checklist:** [PHASE17_2_1_ORACLE_FREE_SETUP_CHECKLIST.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_1_ORACLE_FREE_SETUP_CHECKLIST.md)
- **Free Resource Budget Report:** [PHASE17_2_1_FREE_RESOURCE_BUDGET_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_1_FREE_RESOURCE_BUDGET_REPORT.md)
- **DNS & TLS Readiness Report:** [PHASE17_2_1_DNS_TLS_READINESS_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_1_DNS_TLS_READINESS_REPORT.md)
- **Deployment Command Plan:** [PHASE17_2_1_DEPLOYMENT_COMMAND_PLAN.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_1_DEPLOYMENT_COMMAND_PLAN.md)
- **Final Readiness Report:** [PHASE17_2_1_FINAL_READINESS_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_1_FINAL_READINESS_REPORT.md)
- **Current Architecture Audit:** [PHASE17_2_CURRENT_ARCHITECTURE_AUDIT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_CURRENT_ARCHITECTURE_AUDIT.md)
- **Zero-Cost Architecture Plan:** [PHASE17_2_FREE_ARCHITECTURE_PLAN.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_FREE_ARCHITECTURE_PLAN.md)
- **ARM64 Compatibility Report:** [PHASE17_2_ARM_COMPATIBILITY_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_ARM_COMPATIBILITY_REPORT.md)
- **Free Cloud Setup Guide:** [PHASE17_2_FREE_CLOUD_SETUP_GUIDE.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_FREE_CLOUD_SETUP_GUIDE.md)
- **Free Deployment & Blocker Report:** [PHASE17_2_FREE_CLOUD_DEPLOYMENT_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_FREE_CLOUD_DEPLOYMENT_REPORT.md)
- **Single-Node Disaster Recovery Report:** [PHASE17_2_FREE_CLOUD_DR_REPORT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_FREE_CLOUD_DR_REPORT.md)
- **Free Cloud Reality Audit:** [PHASE17_2_FREE_CLOUD_REALITY_AUDIT.md](file:///c:/Users/testing/Desktop/AI_Reliability/docs/development/PHASE17_2_FREE_CLOUD_REALITY_AUDIT.md)
