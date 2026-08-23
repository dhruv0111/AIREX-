"""Test-generation execution runner (Phase 5).

The worker calls :meth:`GenerationRunner.run` with a generation request id. The
runner reuses the Model Gateway (never provider SDKs directly), freezes source
material from the request snapshot, parses the structured JSON output, dedups by
SHA-256 fingerprint, computes deterministic quality scores, persists
PENDING_REVIEW candidates idempotently, and drives the request state machine.
A crashed generation is never left permanently RUNNING: stale recovery is
provided by :func:`recover_stale_generations` (ADR-021/023).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.encryption import decrypt_credentials
from app.core.metrics import (
    generation_candidates_duplicates_total,
    generation_candidates_rejected_total,
    generation_candidates_total,
    generation_duration_seconds,
    generation_errors_total,
    generation_provider_requests_total,
    generation_requests_total,
)
from app.generation.candidate import compute_quality_score, fingerprint_candidate
from app.generation.parser import GenerationParseError, parse_generation_output
from app.generation.prompts import build_generation_messages, render_source_material
from app.integrations.gateway import ModelGatewayService
from app.integrations.provider import ErrorCategory, ModelRequest, ProviderError
from app.repositories.audit import AuditRepository
from app.repositories.generation import (
    GeneratedCandidateRepository,
    GenerationRequestRepository,
)
from app.repositories.project import ProjectRepository
from app.repositories.provider import ProviderRepository

logger = logging.getLogger("airex.generation")


class GenerationRunner:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._settings = get_settings()
        self._gateway = ModelGatewayService(self._settings)

    async def run(self, request_id: UUID) -> dict[str, Any]:
        """Execute a generation request. Idempotent for terminal requests.

        ``request_id`` may arrive as a string (worker payload from JSON);
        normalize it to a :class:`uuid.UUID` so the Uuid-typed primary key binds
        correctly.
        """
        if isinstance(request_id, str):
            request_id = UUID(request_id)
        start = time.perf_counter()
        async with self._session_factory() as session:
            repo = GenerationRequestRepository(session)
            request = await repo.get_by_id(request_id)
            if request is None:
                return {"status": "NOT_FOUND"}
            if request.status in ("COMPLETED", "FAILED", "CANCELLED"):
                return {"status": request.status, "idempotent": True}

            if request.status == "QUEUED":
                await repo.set_status(request, "RUNNING")
                await AuditRepository(session).record(
                    action="GENERATION_STARTED",
                    organization_id=None,
                    user_id=request.created_by,
                    resource_type="generation_request",
                    resource_id=request.id,
                )
                generation_requests_total.labels(status="RUNNING").inc()
                await session.commit()

            try:
                return await self._execute(session, request, start)
            except GenerationParseError as exc:
                logger.warning(
                    "generation output unparseable",
                    extra={"request_id": str(request_id), "reason": str(exc)},
                )
                await self._mark_failed(session, request, str(exc)[:1000], "PARSE_ERROR")
                return {"status": "FAILED", "category": "PARSE_ERROR"}
            except ProviderError as exc:
                category = (
                    "TIMEOUT" if exc.category is ErrorCategory.TIMEOUT_ERROR else "PROVIDER_ERROR"
                )
                logger.warning(
                    "generation provider error",
                    extra={"request_id": str(request_id), "category": category},
                )
                await self._mark_failed(session, request, str(exc)[:1000], category)
                return {"status": "FAILED", "category": category}
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("generation request failed", extra={"request_id": str(request_id)})
                await self._mark_failed(session, request, str(exc)[:1000], "GENERATION_ERROR")
                return {"status": "FAILED", "category": "GENERATION_ERROR"}

    async def _mark_failed(
        self, session: AsyncSession, request, reason: str, category: str
    ) -> None:
        repo = GenerationRequestRepository(session)
        await repo.set_status(request, "FAILED")
        await AuditRepository(session).record(
            action="GENERATION_FAILED",
            organization_id=None,
            user_id=request.created_by,
            resource_type="generation_request",
            resource_id=request.id,
            metadata={"reason": reason, "category": category},
        )
        generation_requests_total.labels(status="FAILED").inc()
        generation_errors_total.labels(category=category).inc()
        await session.commit()

    async def _execute(self, session: AsyncSession, request, start: float) -> dict[str, Any]:
        repo = GenerationRequestRepository(session)
        candidates_repo = GeneratedCandidateRepository(session)
        projects = ProjectRepository(session)
        providers = ProviderRepository(session)

        snapshot = request.generator_model_snapshot or {}
        project = await projects.get_by_id(request.project_id)
        org_id = project.organization_id if project is not None else None
        provider = None
        if snapshot.get("provider_id") and org_id is not None:
            # snapshot is JSON, so provider_id is a string.
            provider = await providers.get_for_organization(
                UUID(str(snapshot["provider_id"])), org_id
            )
        api_key = (
            decrypt_credentials(provider.encrypted_credentials)
            if provider is not None and provider.encrypted_credentials
            else None
        )

        config = request.configuration or {}
        count = int(config.get("count") or request.count or 1)
        generation_types = config.get("generation_types") or [request.generation_type]
        difficulty_distribution = config.get("difficulty_distribution")
        source_snapshot = request.source_snapshot or {}
        records = source_snapshot.get("records") or []

        messages = build_generation_messages(
            instruction=request.instruction,
            generation_type=",".join(str(t) for t in generation_types),
            difficulty_distribution=difficulty_distribution,
            source_material=render_source_material(records),
            count=count,
        )
        model_request = ModelRequest(
            model=str(snapshot.get("model_identifier") or ""),
            messages=messages,
            temperature=snapshot.get("temperature"),
            max_tokens=snapshot.get("max_tokens"),
            top_p=snapshot.get("top_p"),
            timeout=float(self._settings.generation_timeout_seconds),
        )
        generation_provider_requests_total.inc()
        response = await self._gateway.invoke(
            provider_type=str(snapshot.get("provider_type") or "LOCAL"),
            api_key=api_key,
            base_url=snapshot.get("base_url"),
            configuration=snapshot.get("configuration") or {},
            request=model_request,
        )

        valid, rejected = parse_generation_output(response.content, request.generation_type)
        generation_candidates_rejected_total.inc(rejected)

        # Persist candidates with fingerprint dedup + deterministic quality score.
        seen: dict[str, UUID] = {}
        created = 0
        duplicates = 0
        for item in valid:
            fingerprint = fingerprint_candidate(
                input_text=item["input"],
                expected_output=item["expected_output"],
                context=item["context"],
            )
            duplicate_of = seen.get(fingerprint)
            if duplicate_of is None:
                existing = await candidates_repo.get_by_fingerprint(request.id, fingerprint)
                duplicate_of = existing.id if existing is not None else None
            if duplicate_of is not None:
                duplicates += 1
                await candidates_repo.create(
                    generation_request_id=request.id,
                    project_id=request.project_id,
                    input_text=item["input"],
                    expected_output=item["expected_output"],
                    context=item["context"],
                    category=item["category"],
                    generation_type=item["generation_type"],
                    difficulty=item["difficulty"],
                    status="PENDING_REVIEW",
                    quality_score=0.0,
                    fingerprint=fingerprint,
                    duplicate_of=duplicate_of,
                    metadata={"duplicate": True},
                )
                continue
            candidate = await candidates_repo.create(
                generation_request_id=request.id,
                project_id=request.project_id,
                input_text=item["input"],
                expected_output=item["expected_output"],
                context=item["context"],
                category=item["category"],
                generation_type=item["generation_type"],
                difficulty=item["difficulty"],
                status="PENDING_REVIEW",
                quality_score=compute_quality_score(item),
                fingerprint=fingerprint,
            )
            seen[fingerprint] = candidate.id
            created += 1

        await repo.touch_heartbeat(request)
        await repo.set_status(request, "COMPLETED")
        await AuditRepository(session).record(
            action="GENERATION_COMPLETED",
            organization_id=None,
            user_id=request.created_by,
            resource_type="generation_request",
            resource_id=request.id,
            metadata={"created": created, "duplicates": duplicates, "rejected": rejected},
        )
        generation_requests_total.labels(status="COMPLETED").inc()
        generation_candidates_total.labels(status="PENDING_REVIEW").inc(created)
        generation_candidates_duplicates_total.inc(duplicates)
        generation_duration_seconds.observe(time.perf_counter() - start)
        await session.commit()
        return {
            "status": "COMPLETED",
            "created": created,
            "duplicates": duplicates,
            "rejected": rejected,
        }


async def recover_stale_generations(session_factory) -> int:
    """Mark RUNNING generation requests with a stale heartbeat as FAILED.

    Mirrors evaluation stale-run recovery (Phase 3 §50): a crashed worker must
    never leave a generation permanently RUNNING.
    """
    settings = get_settings()
    older_than = datetime.now(UTC) - timedelta(seconds=settings.generation_stale_timeout_seconds)
    count = 0
    async with session_factory() as session:
        repo = GenerationRequestRepository(session)
        stale = await repo.stale_requests(older_than)
        for request in stale:
            await repo.set_status(request, "FAILED")
            await AuditRepository(session).record(
                action="GENERATION_FAILED",
                organization_id=None,
                user_id=request.created_by,
                resource_type="generation_request",
                resource_id=request.id,
                metadata={"reason": "stale heartbeat; recovered by worker"},
            )
            generation_requests_total.labels(status="FAILED").inc()
            generation_errors_total.labels(category="STALE").inc()
            count += 1
        await session.commit()
    return count
