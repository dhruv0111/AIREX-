"""SQLAlchemy models for Governance Policies, Approvals & Access Reviews (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GovernancePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Organization-level governance policies (SSO, token limits, release approvals, etc.)."""

    __tablename__ = "governance_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "version", name="uq_gov_policy_org_name_ver"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)  # DRAFT, ACTIVE, DISABLED, ARCHIVED

    rules: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ApprovalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Lightweight approval request for releases, policies, and sensitive actions."""

    __tablename__ = "approval_requests"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True, nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)  # RELEASE_DECISION, GOVERNANCE_POLICY, PROVIDER_CREDENTIAL
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)  # PENDING, APPROVED, REJECTED, CANCELLED, EXPIRED
    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    required_role: Mapped[str] = mapped_column(String(32), default="ADMIN", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list[ApprovalStep]] = relationship("ApprovalStep", back_populates="request", cascade="all, delete-orphan", lazy="selectin")
    decisions: Mapped[list[ApprovalDecision]] = relationship("ApprovalDecision", back_populates="request", cascade="all, delete-orphan", lazy="selectin")


class ApprovalStep(UUIDPrimaryKeyMixin, Base):
    """Multi-step approval sequence."""

    __tablename__ = "approval_steps"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(32), default="ADMIN", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    decision_id: Mapped[UUID | None] = mapped_column(nullable=True)

    request: Mapped[ApprovalRequest] = relationship("ApprovalRequest", back_populates="steps")


class ApprovalDecision(UUIDPrimaryKeyMixin, Base):
    """Recorded approval/rejection decision by an authorized approver."""

    __tablename__ = "approval_decisions"

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True, nullable=False
    )
    decided_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)  # APPROVED, REJECTED
    comments: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    request: Mapped[ApprovalRequest] = relationship("ApprovalRequest", back_populates="decisions")


class AccessReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Periodic campaign reviewing access permissions, users, teams, and service tokens."""

    __tablename__ = "access_reviews"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True, nullable=False)  # OPEN, IN_REVIEW, COMPLETED, EXPIRED
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[AccessReviewItem]] = relationship("AccessReviewItem", back_populates="review", cascade="all, delete-orphan", lazy="selectin")


class AccessReviewItem(UUIDPrimaryKeyMixin, Base):
    """Individual item within an access review campaign."""

    __tablename__ = "access_review_items"

    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("access_reviews.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)  # USER_MEMBERSHIP, TEAM_MEMBER, PROJECT_ACCESS, SERVICE_TOKEN
    subject_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    subject_name: Mapped[str] = mapped_column(String(255), nullable=False)
    context_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decision: Mapped[str] = mapped_column(String(32), default="NO_ACTION", nullable=False)  # KEEP, REVOKE, NO_ACTION
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    review: Mapped[AccessReview] = relationship("AccessReview", back_populates="items")
