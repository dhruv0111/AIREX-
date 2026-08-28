"""CI/CD and Service Token endpoints router (Phase 7)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.errors import ForbiddenError
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.ci import (
    CIRunCreate,
    CIRunResponse,
    ServiceTokenCreate,
    ServiceTokenCreatedResponse,
    ServiceTokenResponse,
)
from app.services.ci import CIService

router = APIRouter(tags=["ci"])


# ------------------------------------------------------------- Token Management
@router.post(
    "/projects/{project_id}/service-tokens",
    status_code=http_status.HTTP_201_CREATED,
)
async def create_service_token(
    project_id: UUID,
    payload: ServiceTokenCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    token, raw_token = await service.create_token(
        project_id=project_id,
        user_id=user.id,
        organization_id=organization_id,
        name=payload.name,
        scopes=payload.scopes,
        expires_in_days=payload.expires_in_days,
    )
    res = ServiceTokenCreatedResponse(
        id=token.id,
        project_id=token.project_id,
        organization_id=token.organization_id,
        name=token.name,
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        created_at=token.created_at,
        expires_at=token.expires_at,
        revoked_at=token.revoked_at,
        last_used_at=token.last_used_at,
        raw_token=raw_token,
    )
    return ok(res)


@router.get(
    "/projects/{project_id}/service-tokens",
    status_code=http_status.HTTP_200_OK,
)
async def list_service_tokens(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    tokens = await service.list_tokens(
        project_id=project_id,
        user_id=user.id,
        organization_id=organization_id,
    )
    return ok([ServiceTokenResponse.model_validate(t, from_attributes=True) for t in tokens])


@router.delete(
    "/service-tokens/{token_id}",
    status_code=http_status.HTTP_200_OK,
)
async def revoke_service_token(
    token_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    await service.revoke_token(
        token_id=token_id,
        user_id=user.id,
        organization_id=organization_id,
    )
    return ok({"status": "revoked"})


@router.post(
    "/service-tokens/{token_id}/rotate",
    status_code=http_status.HTTP_200_OK,
)
async def rotate_service_token(
    token_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    token, raw_token = await service.rotate_token(
        token_id=token_id,
        user_id=user.id,
        organization_id=organization_id,
    )
    res = ServiceTokenCreatedResponse(
        id=token.id,
        project_id=token.project_id,
        organization_id=token.organization_id,
        name=token.name,
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        created_at=token.created_at,
        expires_at=token.expires_at,
        revoked_at=token.revoked_at,
        last_used_at=token.last_used_at,
        raw_token=raw_token,
    )
    return ok(res)


# ------------------------------------------------------------------ CI Runs API
@router.post(
    "/ci/runs",
    status_code=http_status.HTTP_201_CREATED,
)
async def create_ci_run(
    request: Request,
    payload: CIRunCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # Ensure this endpoint is exclusively triggered by a service token
    if not getattr(request.state, "is_service_token", False):
        raise ForbiddenError("Only service accounts/tokens can create CI runs.")

    project_id = getattr(request.state, "service_token_project_id", None)
    if not project_id:
        raise ForbiddenError("Access denied.")

    service = CIService(session)
    ci_run = await service.create_ci_run(
        project_id=project_id,
        organization_id=organization_id,
        user_id=user.id,
        commit_sha=payload.commit_sha,
        branch=payload.branch,
        repository=payload.repository,
        pull_request_number=payload.pull_request_number,
        pull_request_url=payload.pull_request_url,
        ci_provider=payload.ci_provider,
        ci_run_id=payload.ci_run_id,
        ci_job_id=payload.ci_job_id,
        experiment_config=payload.experiment_config,
        idempotency_key=payload.idempotency_key,
    )

    return ok(CIRunResponse.model_validate(ci_run, from_attributes=True))


@router.get(
    "/ci/runs/{id}",
    status_code=http_status.HTTP_200_OK,
)
async def get_ci_run(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    ci_run = await service.get_ci_run(
        run_id=id,
        organization_id=organization_id,
    )
    return ok(CIRunResponse.model_validate(ci_run, from_attributes=True))


@router.post(
    "/ci/runs/{id}/cancel",
    status_code=http_status.HTTP_200_OK,
)
async def cancel_ci_run(
    id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    ci_run = await service.get_ci_run(run_id=id, organization_id=organization_id)
    
    if ci_run.status == "RUNNING" and ci_run.experiment_run_id:
        from app.services.experiment import ExperimentService
        exp_service = ExperimentService(session)
        await exp_service.cancel_run(
            organization_id=organization_id,
            run_id=ci_run.experiment_run_id,
            user_id=user.id,
        )
        ci_run.status = "CANCELLED"
        ci_run.outcome = "FAIL"
        
        await session.commit()
    
    return ok(CIRunResponse.model_validate(ci_run, from_attributes=True))


@router.get(
    "/projects/{project_id}/ci-runs",
    status_code=http_status.HTTP_200_OK,
)
async def list_ci_runs(
    project_id: UUID,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = CIService(session)
    runs, total = await service.list_ci_runs(
        project_id=project_id,
        organization_id=organization_id,
        page=page,
        page_size=page_size,
    )
    res_data = [CIRunResponse.model_validate(r, from_attributes=True) for r in runs]
    return ok_list(res_data, total=total, page=page, page_size=page_size)
