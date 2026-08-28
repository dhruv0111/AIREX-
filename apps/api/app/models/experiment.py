"""Experiment, prompt and prompt version models (spec §21–§23; Phase 6)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED','INCONCLUSIVE')",
            name="ck_experiment_status",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    dataset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL"), nullable=True
    )
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    experiment_type: Mapped[str] = mapped_column(String(50), default="MODEL_COMPARISON", nullable=False)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_of: Mapped[UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExperimentVariant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "experiment_variants"
    __table_args__ = (
        CheckConstraint(
            "variant_type IN ('BASELINE','CANDIDATE')",
            name="ck_variant_type",
        ),
        UniqueConstraint("experiment_id", "variant_type", name="uq_experiment_variant_type"),
    )

    experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_type: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL"), nullable=True
    )
    prompt_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL"), nullable=True
    )
    dataset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True
    )
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ExperimentRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "experiment_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_experiment_run_status",
        ),
    )

    experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True, nullable=False)
    baseline_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    candidate_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ExperimentComparison(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_comparisons"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_difference: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_difference: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification: Mapped[str] = mapped_column(String(50), nullable=False)
    statistical_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Regression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "regressions"

    comparison_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiment_comparisons.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class QualityGate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quality_gates"

    experiment_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    gate_type: Mapped[str] = mapped_column(String(50), default="CANDIDATE_VALUE", nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class QualityGateResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quality_gate_results"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    quality_gate_id: Mapped[UUID] = mapped_column(
        ForeignKey("quality_gates.id", ondelete="CASCADE"), index=True, nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    actual_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class Prompt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompts"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class PromptVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version_number", name="uq_prompt_version_no"),)

    prompt_id: Mapped[UUID] = mapped_column(
        ForeignKey("prompts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(primary_key=False, nullable=False)
    content: Mapped[str] = mapped_column(String(16000), nullable=False)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
