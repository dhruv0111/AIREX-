"""REST API endpoints for Governance Policies, Approvals & Access Reviews (Phase 13)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.permissions import (
    Role,
    require_capability,
    CAP_MANAGE_GOVERNANCE,
    CAP_ACT_APPROVALS,
    CAP_MANAGE_REVIEWS,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.governance import (
    AccessReviewCreate,
    AccessReviewItemDecisionRequest,
    AccessReviewItemResponse,
    AccessReviewResponse,
    ApprovalActionRequest,
    ApprovalDecisionResponse,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    GovernancePolicyCreate,
    GovernancePolicyResponse,
)
from app.services.governance_service import GovernanceService
from app.services.organization import OrganizationService

router = APIRouter(tags=["governance"])


# ---------------------------------------------------------------------------
# Governance Policies
# ---------------------------------------------------------------------------
@router.post("/governance-policies", response_model=GovernancePolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_governance_policy(
    payload: GovernancePolicyCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> GovernancePolicyResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_GOVERNANCE)

    service = GovernanceService(session)
    policy = await service.create_policy(org_id, user.id, payload.model_dump())
    return GovernancePolicyResponse.model_validate(policy)


@router.get("/governance-policies", response_model=list[GovernancePolicyResponse])
async def list_governance_policies(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[GovernancePolicyResponse]:
    service = GovernanceService(session)
    policies = await service.list_policies(org_id)
    return [GovernancePolicyResponse.model_validate(p) for p in policies]


@router.get("/governance-policies/{policy_id}", response_model=GovernancePolicyResponse)
async def get_governance_policy(
    policy_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> GovernancePolicyResponse:
    service = GovernanceService(session)
    policy = await service.get_policy(org_id, policy_id)
    return GovernancePolicyResponse.model_validate(policy)


@router.post("/governance-policies/{policy_id}/activate", response_model=GovernancePolicyResponse)
async def activate_governance_policy(
    policy_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> GovernancePolicyResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_GOVERNANCE)

    service = GovernanceService(session)
    policy = await service.activate_policy(org_id, policy_id, user.id)
    return GovernancePolicyResponse.model_validate(policy)


@router.post("/governance-policies/{policy_id}/disable", response_model=GovernancePolicyResponse)
async def disable_governance_policy(
    policy_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> GovernancePolicyResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_GOVERNANCE)

    service = GovernanceService(session)
    policy = await service.disable_policy(org_id, policy_id, user.id)
    return GovernancePolicyResponse.model_validate(policy)


# ---------------------------------------------------------------------------
# Approval Workflows
# ---------------------------------------------------------------------------
def _serialize_approval(req, session: AsyncSession) -> ApprovalRequestResponse:
    decisions = []
    for d in req.decisions:
        decisions.append(ApprovalDecisionResponse(
            id=d.id,
            request_id=d.request_id,
            decided_by=d.decided_by,
            outcome=d.outcome,
            comments=d.comments,
            decided_at=d.decided_at,
        ))

    return ApprovalRequestResponse(
        id=req.id,
        organization_id=req.organization_id,
        project_id=req.project_id,
        target_type=req.target_type,
        target_id=req.target_id,
        title=req.title,
        description=req.description,
        status=req.status,
        requester_id=req.requester_id,
        required_role=req.required_role,
        expires_at=req.expires_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
        decisions=decisions,
    )


@router.post("/approvals", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_approval_request(
    payload: ApprovalRequestCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ApprovalRequestResponse:
    service = GovernanceService(session)
    req = await service.create_approval_request(org_id, user.id, payload.model_dump())
    return _serialize_approval(req, session)


@router.get("/approvals", response_model=list[ApprovalRequestResponse])
async def list_approval_requests(
    status: str | None = None,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[ApprovalRequestResponse]:
    service = GovernanceService(session)
    reqs = await service.list_approval_requests(org_id, status=status)
    return [_serialize_approval(r, session) for r in reqs]


@router.get("/approvals/{request_id}", response_model=ApprovalRequestResponse)
async def get_approval_request(
    request_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ApprovalRequestResponse:
    service = GovernanceService(session)
    req = await service.get_approval_request(org_id, request_id)
    return _serialize_approval(req, session)


@router.post("/approvals/{request_id}/action", response_model=ApprovalRequestResponse)
async def act_on_approval_request(
    request_id: UUID,
    payload: ApprovalActionRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ApprovalRequestResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_ACT_APPROVALS)

    service = GovernanceService(session)
    req = await service.act_on_approval(org_id, request_id, user.id, payload.outcome, payload.comments)
    return _serialize_approval(req, session)


# ---------------------------------------------------------------------------
# Access Reviews
# ---------------------------------------------------------------------------
def _serialize_review(rev) -> AccessReviewResponse:
    items = []
    for item in rev.items:
        items.append(AccessReviewItemResponse(
            id=item.id,
            review_id=item.review_id,
            item_type=item.item_type,
            subject_id=item.subject_id,
            subject_name=item.subject_name,
            context_info=item.context_info,
            decision=item.decision,
            decided_by=item.decided_by,
            decided_at=item.decided_at,
            notes=item.notes,
        ))

    return AccessReviewResponse(
        id=rev.id,
        organization_id=rev.organization_id,
        title=rev.title,
        status=rev.status,
        due_date=rev.due_date,
        created_by=rev.created_by,
        completed_at=rev.completed_at,
        created_at=rev.created_at,
        updated_at=rev.updated_at,
        items=items,
    )


@router.post("/access-reviews", response_model=AccessReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_access_review(
    payload: AccessReviewCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> AccessReviewResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_REVIEWS)

    service = GovernanceService(session)
    review = await service.create_access_review(org_id, user.id, payload.title, payload.due_date)
    return _serialize_review(review)


@router.get("/access-reviews", response_model=list[AccessReviewResponse])
async def list_access_reviews(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[AccessReviewResponse]:
    service = GovernanceService(session)
    reviews = await service.list_access_reviews(org_id)
    return [_serialize_review(r) for r in reviews]


@router.get("/access-reviews/{review_id}", response_model=AccessReviewResponse)
async def get_access_review(
    review_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> AccessReviewResponse:
    service = GovernanceService(session)
    review = await service.get_access_review(org_id, review_id)
    return _serialize_review(review)


@router.post("/access-reviews/{review_id}/items/{item_id}/decision", response_model=AccessReviewItemResponse)
async def record_access_review_item_decision(
    review_id: UUID,
    item_id: UUID,
    payload: AccessReviewItemDecisionRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> AccessReviewItemResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_REVIEWS)

    service = GovernanceService(session)
    item = await service.decide_item(org_id, review_id, item_id, user.id, payload.decision, payload.notes)
    return AccessReviewItemResponse.model_validate(item)


@router.post("/access-reviews/{review_id}/complete", response_model=AccessReviewResponse)
async def complete_access_review(
    review_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> AccessReviewResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_REVIEWS)

    service = GovernanceService(session)
    review = await service.complete_access_review(org_id, review_id, user.id)
    return _serialize_review(review)
