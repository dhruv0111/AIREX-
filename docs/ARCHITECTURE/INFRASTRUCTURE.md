# Infrastructure — AIREX

Deployment, CI/CD, monitoring, disaster recovery, and scaling for AIREX. **Local-first, zero-cost:** the full stack runs with Docker Compose using free software; production targets AWS (PRD §67) but is optional for development. Kubernetes is V2 (PRD §97).

---

## 1. Environments

| Environment | Purpose | Provisioning |
|-------------|---------|--------------|
| **Local (dev)** | Full-stack development, no external accounts | `docker compose up` (api, web, worker, postgres, redis, minio, mailhog, ollama) |
| **CI** | Automated tests + coverage gates | GitHub Actions ephemeral services (Postgres/Redis containers, Ollama) |
| **Staging** | Pre-prod validation, E2E, security scans | Docker Compose or AWS (optional) |
| **Production** | 99.5%+ availability (PRD §88) | AWS (ECS Fargate or EKS-V2), managed RDS, ElastiCache, S3 |

---

## 2. Service Topology (Production, per PRD §66)

```
Internet ──► CDN / ALB (TLS)
               │
        ┌──────┴──────┐
        ▼             ▼
   Web App        API Server(s)      ← autoscaling group; 2+ AZs
   (Next.js)      (FastAPI)
                    │  │  │
        ┌───────────┘  │  └────────────┐
        ▼              ▼               ▼
   RDS PostgreSQL   ElastiCache     Arq Workers
   (+pgvector)      Redis 7         (autoscaling)
        ▲              ▲               │
        │              │               ▼
   S3 (artifacts)  (jobs/cache)   Model Gateway
        │                          ┌───┴───┐
   SES (mail)                  Ollama/local  Paid providers (optional)
                                   │
                              Prometheus ◄── OTel Collector ◄── all services
                                   │
                              Grafana
```

## 3. Container & Orchestration

- **Dev/self-host:** Docker Compose with profiles (`--profile observability`, `--profile ai` for Ollama). Single command bootstrap.
- **Production (MVP):** AWS ECS Fargate (simpler than EKS for a modular monolith) with:
  - `web` (Next.js standalone) task
  - `api` task (autoscaling by CPU/RPS)
  - `worker` task (autoscaling by queue depth)
  - RDS PostgreSQL (Multi-AZ), ElastiCache Redis (Multi-AZ, AOF), S3 + CloudFront
- **V2 (PRD §97):** migrate to EKS with the same containers (Helm chart) when scale demands.

## 4. Configuration & Secrets

- `pydantic-settings` reads env; `settings.local.yaml` for dev, injected env in prod.
- Secrets (provider keys, DB passwords, JWT keys, encryption keys): local `.env`/Docker secrets in dev; **AWS Secrets Manager / SSM Parameter Store** in prod. Provider API keys remain user-entered data (encrypted with the org encryption key) — see [`SECURITY_ARCHITECTURE.md`](./SECURITY_ARCHITECTURE.md).

## 5. Health Checks (PRD §65)

| Endpoint | Check |
|----------|-------|
| `/live` | Process alive |
| `/ready` | DB reachable, Redis reachable, migrations current |
| `/health` | Aggregate health incl. object storage + provider connectivity (degraded flag) |

Used by LB target groups, ECS health checks, and k8s probes (V2).

## 6. Observability (PRD §64)

| Signal | Tool | Exported by |
|--------|------|-------------|
| Traces | OpenTelemetry (OTLP) → Collector | API, workers, model gateway, workers |
| Metrics | Prometheus (scrape via `/metrics`) | API, workers, queue depth, Redis/DB exporters |
| Dashboards | Grafana | API latency, worker latency, queue depth, error rate, DB perf, Redis health, provider health, evaluation throughput (§64) |
| Logs | Structured JSON to stdout → Loki (optional) | All services (no secrets, §94) |

## 7. CI/CD (PRD §38–§40, §67)

Pipeline (GitHub Actions):

```
Push ─► Lint/typecheck ─► Unit+coverage ─► Integration (Postgres/Redis/Ollama)
      ─► Security scans (SAST, deps, secrets, container) ─► E2E (§109 journey)
      ─► Build & push images ─► Deploy staging ─► Deploy prod (tagged)
```

- **CI quality gate for the product itself:** coverage thresholds (backend ≥80%, critical/engine ≥90% — §91); gate failures block merge.
- **AIREX-in-CI integration (product feature):** the platform exposes a trigger via API/CLI (`airex evaluate run --dataset vX --model …`), returns result, and enforces the quality gate (AC-CICD-001..005, §39). Sample GitHub Action workflow ships with the repo.
- Image builds: Docker multi-stage; `trivy` scan; pinned base images; minimal runtime images.

## 8. Disaster Recovery

| Asset | Strategy | RPO / RTO |
|-------|----------|-----------|
| PostgreSQL | Multi-AZ; daily snapshot + WAL/PITR; cross-region copy | RPO ≤ 5 min, RTO ≤ 1 h |
| Redis | AOF; considered ephemeral (jobs re-enqueued from DB state; cache rebuilt) | RPO ~0 (state in DB) |
| S3 artifacts | Versioning + cross-region replication | RPO ~0 |
| Config/secrets | SSM/Secrets Manager with backup | — |
| Application | Stateless containers; redeploy from images + migrations | RTO ≤ 1 h |
| **Recovery playbooks** | Documented: DB restore, migration rollback, queue drain, provider-key rotation, audit continuity | — |

- **Evaluation-job resilience (PRD §88–§89):** jobs enqueued in Redis survive API restarts; per-test results persisted in Postgres immediately → no partial loss on worker crash; on restart, workers re-enqueue unfinished jobs (idempotent run keys).

## 9. Scaling Strategy

| Layer | Scale trigger | Mechanism |
|-------|---------------|-----------|
| API | CPU/RPS | Horizontal replicas behind ALB (stateless) |
| Workers | Queue depth | Horizontal worker tasks; per-org concurrency budgets (§62) |
| PostgreSQL | Read load | Read replicas (dashboards read replica), connection pooling (pgbouncer) |
| Redis | Memory/throughput | Cluster mode (prod) |
| Object storage | Volume | S3 native scale |
| Trace/metrics | Volume | Table partitioning + retention purge (§DATABASE) |

- **Availability target 99.5% (§88):** multi-AZ, health-based routing, autoscaling, managed services.
- **Ambiguity resolution (AMB-SCALE-001):** MVP concurrency defaults — 10 concurrent evaluations/org, worker autoscale to 20 workers max, per-provider semaphore 8.

## 10. Cost Model

| Tier | Cost |
|------|------|
| **Local dev** | $0 (Postgres, Redis, MinIO, MailHog, Ollama all free/self-hosted; Next.js/FastAPI free) |
| **CI** | Free (GitHub Actions minutes on public repo / within free quota) |
| **Staging** | Minimal (small containers; optional) |
| **Production (MVP)** | AWS managed services: ~$150–$400/mo small footprint (2 AZ, small RDS, ElastiCache, Fargate, S3) — optional for MVP; self-host Docker Compose on a VPS is a zero-cost alternative |

**Zero-cost fallback:** full production parity can be self-hosted on a single VPS with Docker Compose (Postgres/Redis/MinIO/MailHog/Ollama), keeping the same codebase — no AWS required until scale demands.

## 11. Deployment Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| Docker Compose first | Zero-cost local/self-host parity | Cloud-only | Compose not prod-grade at scale | Free | Moderate | Secrets via env |
| ECS Fargate for MVP prod | Simpler than EKS for modular monolith; matches PRD §66 | EKS (V2 §97), EC2 | Fargate limits (rare) | Paid (optional) | Good | IAM roles, private subnets |
| Managed RDS + ElastiCache | Multi-AZ, backups, PITR for 99.5% (§88) | Self-managed on EC2 | Cost | Paid (optional) | Strong | Encryption, RLS |
| Multi-AZ stateless replicas | Availability + scale | Single instance | Cost | Paid (optional) | Strong | — |
| OTel + Prometheus + Grafana | PRD §64 zero-cost self-observability | Datadog (paid) | More ops to maintain | Free | Scales with pull model | — |
