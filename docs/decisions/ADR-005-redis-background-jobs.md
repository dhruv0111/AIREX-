# ADR-005: Redis-Backed Background Jobs

**Status:** Accepted

## Context
Evaluation and other heavy work must never run inside an HTTP request (PRD §56–§57, spec §2.3). The worker abstraction must be replaceable later (spec §4: "worker abstraction must be isolated so the queue implementation can later be replaced").

## Decision
Use **Redis** for the queue and a thin, protocol-isolated `TaskQueue` abstraction (`RedisTaskQueue` + `InMemoryTaskQueue` for tests). A dedicated worker process consumes tasks from a registry. The abstraction allows Celery/RQ/Arq to replace the transport later without touching producers or task handlers.

## Alternatives
- Celery/RQ — heavier; RQ has poor Windows worker support; Celery adds broker/beat complexity.
- Arq — async-native but less portable; deferred as a replacement option.
- SQS/Kafka — paid/overkill for MVP.

## Consequences
- Pros: zero extra infrastructure, portable abstraction, works locally with Docker Redis or in-memory.
- Cons: Redis isn't a durable queue by itself; mitigated by idempotent consumers and the transactional outbox in later phases.
