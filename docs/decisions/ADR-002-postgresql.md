# ADR-002: PostgreSQL as the Primary Database

**Status:** Accepted

## Context
AIREX requires relational integrity (tenancy, versioning, immutability), JSON flexibility (configurations, metrics), and vector storage for RAG (PRD §53–§54).

## Decision
Use **PostgreSQL 16 + pgvector** as the single primary store. ORM: SQLAlchemy 2 (async). Migrations: Alembic. For local development without Postgres, a SQLite fallback (`aiosqlite`) is supported for tests; production and the Docker stack use PostgreSQL.

## Alternatives
- MySQL/NoSQL — weaker JSONB/vector support.
- Separate vector database — deferred; pgvector covers MVP (PRD §54 "pgvector initially").

## Consequences
- Pros: strong ACID, JSONB, pgvector, mature async drivers (asyncpg on Python 3.14 confirmed).
- Cons: requires a running Postgres for the full stack; SQLite fallback has minor dialect differences (documented).
