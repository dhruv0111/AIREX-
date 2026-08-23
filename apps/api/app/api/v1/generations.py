"""Test-generation endpoints (Phase 5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.errors import ValidationFailure
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.generation import (
    CandidateReview,
    CreateDatasetVersionFromCandidates,
    GenerationCreate,
)
from app.services.generation import GenerationService

router = APIRouter(tags=["generations"])


@router.post("/generations", status_code=http_status.HTTP_201_CREATED)
async def create_generation(
    payload: GenerationCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = GenerationService(session)
    request = await service.create(
        organization_id=organization_id, user_id=user.id, payload=payload
    )
    return ok(request)


@router.get("/generations", status_code=http_status.HTTP_200_OK)
async def list_generations(
    project_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    generation_type: str | None = None,
    source_type: str | None = None,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if page < 1 or page_size < 1:
        raise ValidationFailure("page and page_size must be positive.")
    service = GenerationService(session)
    requests, total = await service.list_requests(
        organization_id=organization_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        project_id=project_id,
        status=status,
        generation_type=generation_type,
        source_type=source_type,
    )
    return ok_list(requests, page=page, page_size=page_size, total=total)


@router.get("/generations/{generation_id}", status_code=http_status.HTTP_200_OK)
async def get_generation(
    generation_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = GenerationService(session)
    request = await service.get(
        organization_id=organization_id, request_id=generation_id, user_id=user.id
    )
    return ok(request)


@router.post("/generations/{generation_id}/cancel", status_code=http_status.HTTP_200_OK)
async def cancel_generation(
    generation_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = GenerationService(session)
    request = await service.cancel(
        organization_id=organization_id, request_id=generation_id, user_id=user.id
    )
    return ok(request)


@router.get("/generations/{generation_id}/candidates", status_code=http_status.HTTP_200_OK)
async def list_candidates(
    generation_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    category: str | None = None,
    difficulty: str | None = None,
    generation_type: str | None = None,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if page < 1 or page_size < 1:
        raise ValidationFailure("page and page_size must be positive.")
    service = GenerationService(session)
    candidates, total = await service.candidates(
        organization_id=organization_id,
        request_id=generation_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        status=status,
        category=category,
        difficulty=difficulty,
        generation_type=generation_type,
    )
    return ok_list(candidates, page=page, page_size=page_size, total=total)


@router.get("/candidates/{candidate_id}", status_code=http_status.HTTP_200_OK)
async def get_candidate(
    candidate_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = GenerationService(session)
    candidate = await service.get_candidate(
        organization_id=organization_id, candidate_id=candidate_id, user_id=user.id
    )
    return ok(candidate)


@router.post("/candidates/{candidate_id}/review", status_code=http_status.HTTP_200_OK)
async def review_candidate(
    candidate_id: UUID,
    payload: CandidateReview,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = GenerationService(session)
    candidate = await service.review_candidate(
        organization_id=organization_id,
        candidate_id=candidate_id,
        user_id=user.id,
        action=payload.action,
    )
    return ok(candidate)


@router.post(
    "/generations/{generation_id}/dataset-version",
    status_code=http_status.HTTP_201_CREATED,
)
async def create_dataset_version_from_candidates(
    generation_id: UUID,
    payload: CreateDatasetVersionFromCandidates,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a dataset version from APPROVED generated candidates (ADR-022)."""
    service = GenerationService(session)
    result = await service.create_dataset_version_from_candidates(
        organization_id=organization_id, user_id=user.id, payload=payload
    )
    return ok(result)
