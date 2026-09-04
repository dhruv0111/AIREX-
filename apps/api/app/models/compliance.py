"""Compliance, Audit Intelligence & Data Governance Models (spec Phase 14)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ComplianceFramework(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_frameworks"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. SOC2, ISO_27001, GDPR, HIPAA_READY, INTERNAL_POLICY, CUSTOM
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)  # DRAFT, ACTIVE, DEPRECATED, RETIRED
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    controls: Mapped[list[ComplianceControl]] = relationship(
        "ComplianceControl", back_populates="framework", cascade="all, delete-orphan"
    )


class ComplianceControl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_controls"

    framework_id: Mapped[UUID] = mapped_column(
        ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    control_id: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. CC-01, IAM-02, ENC-03
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="GOVERNANCE", nullable=False)  # ACCESS_CONTROL, DATA_PROTECTION, AI_SAFETY, OBSERVABILITY, GOVERNANCE
    risk_level: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    applicability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    required_evidence_types: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    evaluation_frequency: Mapped[str] = mapped_column(String(32), default="CONTINUOUS", nullable=False)  # CONTINUOUS, DAILY, WEEKLY, MONTHLY, MANUAL
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="NOT_ASSESSED", nullable=False)  # NOT_ASSESSED, COMPLIANT, PARTIALLY_COMPLIANT, NON_COMPLIANT, NOT_APPLICABLE
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    framework: Mapped[ComplianceFramework] = relationship("ComplianceFramework", back_populates="controls")


class ComplianceEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "compliance_evidence"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    sha256_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(32), default="INTERNAL", nullable=False)  # PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    validity_window_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(32), default="FRESH", nullable=False)  # FRESH, STALE, EXPIRED
    integrity_status: Mapped[str] = mapped_column(String(32), default="VALID", nullable=False)  # VALID, TAMPERED, MISSING_SOURCE, STALE
    metadata_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RetentionPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retention_policies"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # traces, evaluations, agent_trajectories, candidates, audit_logs, compliance_evidence
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class LegalHold(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "legal_holds"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_resource_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    placed_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ComplianceAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_assessments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    framework_id: Mapped[UUID] = mapped_column(
        ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)  # DRAFT, IN_PROGRESS, READY_FOR_REVIEW, APPROVED, REJECTED, EXPIRED
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assessed_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[ComplianceAssessmentItem]] = relationship(
        "ComplianceAssessmentItem", back_populates="assessment", cascade="all, delete-orphan"
    )


class ComplianceAssessmentItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "compliance_assessment_items"

    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("compliance_assessments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("compliance_controls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="NOT_ASSESSED", nullable=False)  # COMPLIANT, PARTIALLY_COMPLIANT, NON_COMPLIANT, NOT_APPLICABLE, INSUFFICIENT_EVIDENCE
    evidence_references: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    assessment: Mapped[ComplianceAssessment] = relationship("ComplianceAssessment", back_populates="items")


class ComplianceRemediation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_remediations"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    assessment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("compliance_assessments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    control_id: Mapped[UUID] = mapped_column(
        ForeignKey("compliance_controls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)  # OPEN, IN_PROGRESS, RESOLVED, ACCEPTED_RISK, CLOSED
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_risk_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_risk_approver_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_risk_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
