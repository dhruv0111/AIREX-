"""API v1 endpoints for Phase 10 Intelligence & Deployment Decisions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.errors import ForbiddenError, NotFoundError
from app.core.permissions import Role
from app.db.session import get_db
from app.models import User
from app.models.project import Project
from app.repositories.release_decision import ReleaseDecisionRepository
from app.schemas.common import ok, ok_list
from app.schemas.release_decision import (
    ReleasePolicyCreate,
    ReleasePolicyUpdate,
    ReleasePolicyResponse,
    ReleaseDecisionCreate,
    ReleaseDecisionResponse,
    ReleaseEvidenceResponse,
    ReleaseCheckResponse,
    DecisionComparisonResponse,
    ProjectIntelligenceOverviewResponse,
    ProjectIntelligenceActionsResponse,
)
from app.services.intelligence_service import IntelligenceService
from app.services.organization import OrganizationService

router = APIRouter(tags=["intelligence"])


async def _verify_project_access(
    project_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    require_write: bool = False,
) -> Project:
    project = await db.get(Project, project_id)
    if not project or project.organization_id != organization_id:
        raise NotFoundError("Project not found.")

    from app.core.permissions import resolve_user_project_access
    role, _ = await resolve_user_project_access(db, user_id, project_id, organization_id)
    if role is None:
        raise ForbiddenError("You do not have access to this project.")

    if require_write and role == Role.VIEWER:
        raise ForbiddenError("Viewer cannot perform write operations on release decisions or policies.")

    return project


# ------------------------------------------------------------- Release Policies
@router.post("/projects/{project_id}/release-policies", status_code=http_status.HTTP_201_CREATED)
async def create_release_policy(
    project_id: UUID,
    payload: ReleasePolicyCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = IntelligenceService(session)
    policy = await service.create_policy(
        project_id=project_id,
        user_id=user.id,
        **payload.model_dump(),
    )
    return ok(ReleasePolicyResponse.model_validate(policy))


@router.get("/projects/{project_id}/release-policies")
async def list_release_policies(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    policies = await repo.list_policies_by_project(project_id)
    return ok([ReleasePolicyResponse.model_validate(p) for p in policies])


@router.get("/projects/{project_id}/release-policies/{policy_id}")
async def get_release_policy(
    project_id: UUID,
    policy_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    policy = await repo.get_policy_by_id(policy_id)
    if not policy or policy.project_id != project_id:
        raise NotFoundError("Release policy not found.")
    return ok(ReleasePolicyResponse.model_validate(policy))


@router.put("/projects/{project_id}/release-policies/{policy_id}")
async def update_release_policy(
    project_id: UUID,
    policy_id: UUID,
    payload: ReleasePolicyUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    repo = ReleaseDecisionRepository(session)
    policy = await repo.get_policy_by_id(policy_id)
    if not policy or policy.project_id != project_id:
        raise NotFoundError("Release policy not found.")

    service = IntelligenceService(session)
    updated = await service.update_policy(
        policy_id=policy_id,
        user_id=user.id,
        **payload.model_dump(exclude_unset=True),
    )
    return ok(ReleasePolicyResponse.model_validate(updated))


# ------------------------------------------------------------- Release Decisions
@router.post("/projects/{project_id}/release-decisions", status_code=http_status.HTTP_201_CREATED)
async def create_release_decision(
    project_id: UUID,
    payload: ReleaseDecisionCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = IntelligenceService(session)
    decision = await service.create_decision(
        project_id=project_id,
        organization_id=organization_id,
        environment_id=payload.environment_id,
        model_id=payload.model_id,
        release_policy_id=payload.release_policy_id,
        user_id=user.id,
        model_version=payload.model_version,
        model_configuration=payload.model_configuration,
    )
    return ok(ReleaseDecisionResponse.model_validate(decision))


@router.get("/projects/{project_id}/release-decisions")
async def list_release_decisions(
    project_id: UUID,
    environment_id: UUID | None = Query(default=None),
    model_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    decisions = await repo.list_decisions_by_project(
        project_id=project_id,
        environment_id=environment_id,
        model_id=model_id,
    )
    return ok([ReleaseDecisionResponse.model_validate(d) for d in decisions])


@router.get("/projects/{project_id}/release-decisions/{decision_id}")
async def get_release_decision(
    project_id: UUID,
    decision_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    decision = await repo.get_decision_by_id(decision_id)
    if not decision or decision.project_id != project_id:
        raise NotFoundError("Release decision not found.")
    return ok(ReleaseDecisionResponse.model_validate(decision))


@router.post("/projects/{project_id}/release-decisions/{decision_id}/evaluate")
async def evaluate_release_decision_endpoint(
    project_id: UUID,
    decision_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    repo = ReleaseDecisionRepository(session)
    decision = await repo.get_decision_by_id(decision_id)
    if not decision or decision.project_id != project_id:
        raise NotFoundError("Release decision not found.")

    service = IntelligenceService(session)
    evaluated = await service.evaluate_decision(decision_id=decision_id, user_id=user.id)
    return ok(ReleaseDecisionResponse.model_validate(evaluated))


@router.get("/projects/{project_id}/release-decisions/{decision_id}/evidence")
async def get_decision_evidence(
    project_id: UUID,
    decision_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    decision = await repo.get_decision_by_id(decision_id)
    if not decision or decision.project_id != project_id:
        raise NotFoundError("Release decision not found.")
    return ok([ReleaseEvidenceResponse.model_validate(e) for e in decision.evidences])


@router.get("/projects/{project_id}/release-decisions/{decision_id}/checks")
async def get_decision_checks(
    project_id: UUID,
    decision_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    decision = await repo.get_decision_by_id(decision_id)
    if not decision or decision.project_id != project_id:
        raise NotFoundError("Release decision not found.")
    return ok([ReleaseCheckResponse.model_validate(c) for c in decision.checks])


@router.get("/projects/{project_id}/release-decisions/{decision_id}/compare")
async def compare_release_decision(
    project_id: UUID,
    decision_id: UUID,
    previous_decision_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    repo = ReleaseDecisionRepository(session)
    decision = await repo.get_decision_by_id(decision_id)
    if not decision or decision.project_id != project_id:
        raise NotFoundError("Release decision not found.")

    service = IntelligenceService(session)
    comparison = await service.compare_decisions(
        current_id=decision_id,
        previous_id=previous_decision_id,
    )
    return ok(DecisionComparisonResponse.model_validate(comparison))


# ------------------------------------------------------------- Intelligence Dashboard Endpoints
@router.get("/projects/{project_id}/intelligence/overview")
async def get_intelligence_overview(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = IntelligenceService(session)
    overview = await service.get_project_overview(project_id)
    return ok(ProjectIntelligenceOverviewResponse.model_validate(overview))


@router.get("/projects/{project_id}/intelligence/actions")
async def get_intelligence_actions(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = IntelligenceService(session)
    actions = await service.get_project_actions(project_id)
    return ok(ProjectIntelligenceActionsResponse.model_validate({"project_id": project_id, "actions": actions}))
