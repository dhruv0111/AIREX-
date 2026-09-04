# AIREX — AI Reliability, Evaluation & Observability Platform

AIREX is a production-grade platform for testing, evaluating, monitoring, and benchmarking AI applications — particularly LLM and RAG-based systems. It answers three questions for an AI engineering team: *Is my AI good? Did my latest change make it better or worse? Why did it become worse?*

> **Phase 0 — Foundation & Architecture.** Implements the monorepo foundation: backend (FastAPI), frontend (Next.js), PostgreSQL, Redis, worker, authentication, organizations, projects, multi-tenancy, health checks, metrics, migrations, seed, CLI, tests, CI, and documentation.
>
> **Phase 1 — AI Provider & Model Gateway.** Now implemented on top of Phase 0: environment management (one per type), AI provider management with encrypted API-key storage and rotation, model management, and a Model Gateway with provider adapters (Local/OpenAI/Anthropic/Gemini), connection testing, model invocation, normalized error taxonomy, retry with backoff, timeouts, invocation telemetry, and Prometheus model metrics. Later phases (datasets, evaluation engine, RAG, test generation, experiments, observability, research) build on this foundation.
>
> **Phase 8 — Production AI Observability & Alerting.** Now implemented: batched trace/span ingestion, async queue processing, deduplication, sampling, privacy modes (`METADATA_ONLY` / `HASHED_CONTENT` / `FULL_CONTENT`), retention policies, a versioned model pricing cost engine, an observability dashboard, trace explorer + trace detail with span hierarchy, model/provider/cost/latency dashboards, quality signals, an alert engine (threshold → trigger → deduplicate → resolve) with HMAC-signed webhook notifications, RBAC, multi-tenant isolation, audit events, Prometheus metrics, and the official Python SDK (`packages/airex-python`).

## 🚀 Quick Access (Live Development Servers)

| Service | Local URL | Description |
| :--- | :--- | :--- |
| **Frontend Web App** | [http://localhost:3000](http://localhost:3000) | Next.js 15 UI Dashboard & Admin Portal |
| **Backend REST API** | [http://localhost:8000](http://localhost:8000) | FastAPI Core Service |
| **Interactive API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger UI Explorer |
| **Health Probe** | [http://localhost:8000/health/ready](http://localhost:8000/health/ready) | System & Database Readiness |
| **Platform User Guide** | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Complete Feature Walkthrough & Manual |

---

## Table of Contents

- [Quick Access](#-quick-access-live-development-servers)
- [Project Overview](#project-overview)
- [Platform User Guide](docs/USER_GUIDE.md)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Docker Setup](#docker-setup)
- [Database Setup](#database-setup)
- [Running Tests](#running-tests)
- [Running E2E Tests](#running-e2e-tests)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [CLI](#cli)
- [Contribution Guide](#contribution-guide)
- [Security](#security)
- [Roadmap](#roadmap)

---

## Project Overview

AIREX is organized as a monorepo with an API-first architecture:

```
Browser → Next.js → FastAPI → Service Layer → Repository Layer → PostgreSQL
```

Long-running work (evaluation) is never executed in a synchronous HTTP request — it is dispatched to a Redis-backed worker queue.

## Architecture

- [`docs/ARCHITECTURE/`](docs/ARCHITECTURE/README.md) — system, frontend, backend, database, API, security, infrastructure, event, integration architecture, and decisions.
- [`docs/CONTRACTS/`](docs/CONTRACTS/API_CONTRACTS.md) — database schema, ERD, API, error, event, auth, and webhook contracts.
- [`docs/UX/`](docs/UX/README.md) — information architecture, flows, page specs, design system, responsive system.
- [`docs/PRD_ANALYSIS/`](docs/PRD_ANALYSIS/README.md) — requirement inventory, feature inventory, journeys, business rules, permissions, data model, acceptance criteria, ambiguity register.
- [`docs/decisions/`](docs/decisions/ADR-001-modular-monolith.md) — architecture decision records (ADR-001..011).

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, TanStack Query, Recharts |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL 16 + pgvector (SQLite fallback for tests) |
| Queue / Cache | Redis 7 (worker queue, caching, metrics) |
| Worker | Python async worker behind a replaceable `TaskQueue` abstraction |
| Testing | pytest, pytest-asyncio, httpx, Vitest, Playwright |
| Quality | Ruff, Black, MyPy, ESLint, Prettier |
| Infra | Docker, Docker Compose, GitHub Actions |

## Prerequisites

- Docker + Docker Compose
- Python 3.12+ (3.14 supported) for local backend tests
- Node.js 18.17+ (20/22/24 supported) for local frontend

## Installation

```bash
git clone <repository-url>
cd airex

cp .env.example .env

# Linux/macOS:
make setup

# Windows (PowerShell):
.\scripts\setup.ps1
```

After setup:

```
Frontend:    http://localhost:3000
API:         http://localhost:8000
Swagger:     http://localhost:8000/docs
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3001
```

## Environment Variables

See [`.env.example`](.env.example). Never commit `.env`; only `.env.example` is tracked. Key variables:

```env
DATABASE_URL=postgresql+asyncpg://airex:airex@postgres:5432/airex
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY=change-me
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Docker Setup

```bash
docker compose up -d --build     # start the full stack
docker compose ps                # status (postgres, redis, api, worker, web, prometheus, grafana)
docker compose logs -f api       # follow API logs
docker compose down -v           # stop and remove volumes
```

## End-to-End User Guide

New here? Read **[`docs/development/USER_GUIDE.md`](docs/development/USER_GUIDE.md)** — it explains what AIREX does today (Phases 0–5) and walks you step by step from login → project → provider/model → dataset → evaluation → test generation → candidate review → dataset version.

## Database Setup

```bash
# Apply migrations
make migrate            # or: .\scripts\migrate.ps1

# Create a new migration
make migration name="add_thing"   # then review apps/api/alembic/versions/

# Seed demo data (login: demo@example.com / demo-password-123)
make seed               # or: .\scripts\seed.ps1
```

The initial migration `0001_initial_schema` creates all 20 Phase 0 tables; migration `0002_phase1_models_providers_environments` adds provider/model status and credential-version columns, environment configuration, and the `model_invocations` audit table.

## Running Tests

```bash
# Backend (unit + integration + security) — SQLite in-process
cd apps/api
.venv\Scripts\python -m pytest -q          # Windows
python -m pytest -q                        # Linux/macOS

# With coverage
.venv\Scripts\python -m pytest --cov=app --cov-report=term-missing

# Frontend (Vitest)
cd apps/web && npm test

# Lint / format / typecheck
make lint format typecheck
```

Integration tests run against the real API → service → repository → database chain (SQLite by default; PostgreSQL via the Docker test stack when `DATABASE_URL` is set).

## Running E2E Tests

```bash
# Start the full stack first, then:
cd tests/e2e
npm install
npx playwright install chromium
npx playwright test
```

The E2E suite covers the Phase 0 critical journey (register → create project → logout, AT-033/034/035) and the Phase 1 journey (create environment → create local provider → test connection → create model → invoke → latency/tokens rendered, AT-P1-UI-001..013).

## API Documentation

Interactive Swagger UI: `http://localhost:8000/docs` (auto-generated OpenAPI). Contracts: [`docs/CONTRACTS/API_CONTRACTS.md`](docs/CONTRACTS/API_CONTRACTS.md).

## Project Structure

```
airex/
├── apps/
│   ├── web/            # Next.js frontend
│   └── api/            # FastAPI backend (app/, tests/, alembic/)
├── packages/
│   ├── shared-types/   # shared TS types
│   ├── api-client/     # typed API client
│   └── config/         # runtime config
├── infrastructure/     # docker, prometheus, grafana
├── scripts/            # setup/migrate/seed/CLI (sh + ps1)
├── tests/e2e/          # Playwright E2E
├── docs/               # PRD analysis, architecture, contracts, UX, decisions
└── .github/workflows/  # CI + E2E pipelines
```

## Python SDK (Phase 8)

Install the official observability SDK:

```bash
pip install ./packages/airex-python
```

Quick start — instrument a production AI request without ever blocking your application:

```python
from airex import AirexClient

client = AirexClient(project_id="<project-id>", api_token="<service-token>")

with client.trace("chat-completion") as trace:
    with client.observe_llm(model="gpt-4o", provider="openai") as span:
        span.input_tokens = 1000
        span.output_tokens = 500
        # ... your model call ...
```

- The SDK batches events, flushes on size/interval/shutdown, and never blocks production traffic (bounded queue with drop-on-overflow).
- If AIREX is unreachable, observability fails silently — your AI application keeps running (`AIREX_SDK_DISABLED=true` disables the SDK entirely).
- No prompts or responses are sent by default; the SDK only records trace/span metadata and token counts.

## Observability Configuration (Phase 8)

Per-project privacy, retention, and sampling settings are privacy-safe by default:

```text
observability_mode = METADATA_ONLY   # METADATA_ONLY | HASHED_CONTENT | FULL_CONTENT
retention_days      = <unset>        # e.g. 7 / 30 / 90 / 180
sample_rate         = 1.0            # 0.0..1.0 (errors can bypass sampling)
capture_errors      = true
capture_quality_signals = true
```

Manage them via the UI (`/projects/[id]/observability`) or the API:

```bash
curl -X PUT http://localhost:8000/api/v1/projects/<project-id>/observability/settings \
  -H "Authorization: Bearer <token>" -H "X-Organization-Id: <org-id>" \
  -H "Content-Type: application/json" \
  -d '{"observability_mode":"HASHED_CONTENT","retention_days":30,"sample_rate":0.5}'
```

## Ingestion API (Phase 8)

Send deterministic trace + span batches (`202 Accepted` → async worker → PostgreSQL):

```bash
curl -X POST http://localhost:8000/api/v1/observability/ingest \
  -H "Authorization: Bearer <token>" -H "X-Project-Id: <project-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "traces": [{"trace_id":"trace_1","environment":"production","start_time":"2026-01-01T00:00:00Z","status":"SUCCESS"}],
    "spans": [{"trace_id":"trace_1","span_id":"span_1","name":"model-call","span_type":"LLM",
               "provider":"openai","model":"gpt-4o","input_tokens":1000,"output_tokens":500,
               "start_time":"2026-01-01T00:00:00Z","status":"SUCCESS"}]
  }'
```

## Dashboard & Trace Explorer (Phase 8)

- **Dashboard** `/projects/[id]/observability` — requests, success/error rate, latency (p50/p90/p95/p99), tokens, cost, and model/provider breakdowns with selectable time ranges.
- **Trace Explorer** `/projects/[id]/observability/traces` — paginated search by status, provider, trace ID, and time range.
- **Trace Detail** `/projects/[id]/observability/traces/[traceId]` — span hierarchy, LLM token usage, and estimated cost.
- Empty states show *"No observability data yet"* — real `N/A` for missing cost/latency, never fake `$0`.

## Alerts (Phase 8)

- **Alerts** `/projects/[id]/alerts` — active/history lists, severity, occurrence counts, and acknowledgement.
- **Rules** `/projects/[id]/alerts/rules` — create/edit/disable/delete threshold rules (`error_rate`, `latency_p95`, `cost`, `token_usage`, `request_rate`, `quality_score`).
- Alerts are produced by the real alert engine (worker, ~60s cadence): threshold crossing triggers, repeated violations deduplicate into one incident, recovery resolves it, and optional HMAC-signed webhook notifications are dispatched.

## CLI

```bash
python -m app.cli version       # or scripts/airex version
python -m app.cli health
python -m app.cli login
python -m app.cli project list --organization <org-id>
```

## Contribution Guide

1. Follow the layering: API routers must not contain business logic; services orchestrate; repositories own SQL.
2. Never bypass authorization for development convenience; always validate organization membership server-side.
3. Add tests with every change (unit for logic, integration for API↔DB, E2E for critical journeys).
4. Run `make lint format typecheck test` (or the PowerShell equivalents) before pushing.
5. Document decisions in `docs/decisions/` when a new architectural choice is made.

## Security

- Passwords hashed with PBKDF2-SHA256 (pluggable hasher; argon2id planned).
- JWT access + rotating refresh.
- Provider API keys encrypted at rest with Fernet; masked in responses; rotation with credential-version audit (AT-P1-003/004).
- Multi-tenant isolation enforced at the repository layer (AC-SEC-001/002) — cross-org provider/model access returns 404 (Phase 1 security tests).
- SSRF protection validates provider base URLs (blocks private/loopback/metadata ranges).
- Standard error envelope; no stack traces leaked (§63).
- Rate limiting on register/login/model test/invoke.
- Secrets never committed; `.env` ignored.
- Security test suite covers secrets, passwords, SQL injection, XSS, and Phase 1 authorization (cross-org isolation, role gating, secret hygiene).

## Roadmap

Phase 0 (this) → Phase 1 (environments, providers, model gateway) → Phase 2 (datasets, versioning, test cases) → Phase 3 (evaluation engine, metrics, semantics) → Phase 4 (RAG) → Phase 5 (test generation, safety) → Phase 6 (experiments, regression, quality gates) → Phase 7 (CI/CD, CLI) → Phase 8 (observability, alerts — complete) → Phase 9 (RCA, human review) → Phase 10 (research workspace) → Phase 11 (AWS/K8s) → Phase 12 (portfolio).

See [`docs/PRD_ANALYSIS/AMBIGUITY_REGISTER.md`](docs/PRD_ANALYSIS/AMBIGUITY_REGISTER.md) and [`docs/ARCHITECTURE/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE/ARCHITECTURE_DECISIONS.md) for open assumptions to confirm with the product owner.
