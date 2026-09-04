"""Pydantic schemas for Governance Policies, Approvals & Access Reviews (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class GovernancePolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    rules: dict = Field(default_factory=dict)


class GovernancePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    description: str | None = None
    version: int
    status: str
    rules: dict | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalRequestCreate(BaseModel):
    target_type: str = Field(..., min_length=2)  # RELEASE_DECISION, GOVERNANCE_POLICY, PROVIDER_CREDENTIAL
    target_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    project_id: UUID | None = None
    required_role: str = Field(default="ADMIN")


class ApprovalActionRequest(BaseModel):
    outcome: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    comments: str | None = None


class ApprovalDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    decided_by: UUID
    decided_by_name: str | None = None
    outcome: str
    comments: str | None = None
    decided_at: datetime


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID | None = None
    target_type: str
    target_id: str
    title: str
    description: str | None = None
    status: str
    requester_id: UUID
    requester_name: str | None = None
    required_role: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    decisions: list[ApprovalDecisionResponse] = Field(default_factory=list)


class AccessReviewCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    due_date: datetime | None = None


class AccessReviewItemDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(KEEP|REVOKE|NO_ACTION)$")
    notes: str | None = None


class AccessReviewItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    review_id: UUID
    item_type: str
    subject_id: str
    subject_name: str
    context_info: dict | None = None
    decision: str
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    notes: str | None = None


class AccessReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    title: str
    status: str
    due_date: datetime | None = None
    created_by: UUID
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[AccessReviewItemResponse] = Field(default_factory=list)
