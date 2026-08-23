# ADR-001: Modular Monolith Backend

**Status:** Accepted

## Context
AIREX spans many modules (auth, organizations, projects, models, datasets, evaluations, experiments, observability, reports). Microservices were considered but Phase 0 must ship quickly and stay simple while supporting later extraction.

## Decision
Use a **modular monolith**: one FastAPI application exposing the API, a separate worker process, sharing a common `app` package organized by module (`app/api`, `app/services`, `app/repositories`, `app/models`, `app/workers`). Modules are independent packages with explicit boundaries.

## Alternatives
- **Microservices from day one** — high operational cost, premature for MVP.
- **Single process doing everything** — violates async requirements (API must not block on evaluation).
- **Serverless functions** — poor fit for long-running evaluation workers.

## Consequences
- Pros: fast iteration, single deployment, shared domain logic, low overhead.
- Cons: requires discipline to keep module boundaries clean; extraction into services later needs deliberate effort (supported by the port/interface layering).
