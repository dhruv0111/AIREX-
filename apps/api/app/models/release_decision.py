"""SQLAlchemy models for Phase 10: Release Policies, Release Decisions, Release Evidence, and Release Checks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReleasePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "release_policies"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Threshold rules
    min_reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_regression_severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_critical_alerts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_statistical_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_benchmark: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_evaluation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_dataset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True
    )
    required_quality_gates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_evidence_age_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    custom_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ReleaseDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "release_decisions"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    environment_id: Mapped[UUID] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    )
    release_policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("release_policies.id", ondelete="RESTRICT"), nullable=False
    )
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Lifecycle: DRAFT, COLLECTING_EVIDENCE, READY, DECIDED, STALE, SUPERSEDED, FAILED
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True, nullable=False)
    # Outcome: APPROVED, CONDITIONALLY_APPROVED, REJECTED, INSUFFICIENT_EVIDENCE, BLOCKED
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)

    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    readiness_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    stale_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    superseded_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("release_decisions.id", ondelete="SET NULL"), nullable=True
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    evidences: Mapped[list[ReleaseEvidence]] = relationship(
        "ReleaseEvidence", back_populates="decision", cascade="all, delete-orphan", lazy="selectin"
    )
    checks: Mapped[list[ReleaseCheck]] = relationship(
        "ReleaseCheck", back_populates="decision", cascade="all, delete-orphan", lazy="selectin"
    )


class ReleaseEvidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "release_evidences"

    release_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("release_decisions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Source type: EVALUATION, EXPERIMENT, BENCHMARK, OBSERVABILITY, ALERT
    source_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    methodology_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_fresh: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    decision: Mapped[ReleaseDecision] = relationship("ReleaseDecision", back_populates="evidences")


class ReleaseCheck(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "release_checks"

    release_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("release_decisions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Status: PASS, FAIL, WARNING, MISSING, STALE, NOT_APPLICABLE
    status: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    actual_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    decision: Mapped[ReleaseDecision] = relationship("ReleaseDecision", back_populates="checks")
