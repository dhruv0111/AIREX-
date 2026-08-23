# ADR-003: FastAPI for the Backend

**Status:** Accepted

## Context
The PRD specifies Python + FastAPI (PRD §67) and emphasizes type safety, async execution, and auto-generated OpenAPI (PRD §95).

## Decision
Use **FastAPI + Pydantic v2** for the API layer, with SQLAlchemy 2 async for data access. FastAPI auto-generates the OpenAPI/Swagger documentation.

## Alternatives
- Django/DRF — heavier, sync-first.
- Flask — no built-in validation/docs.
- Node/NestJS — leaves the Python AI/ML ecosystem (PRD §67 prefers Python).

## Consequences
- Pros: async-native, Pydantic validation, auto docs, matches PRD stack.
- Cons: younger framework; mitigated by maturity of FastAPI 0.14x and Pydantic 2.x.
