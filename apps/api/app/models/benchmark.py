"""SQLAlchemy models for Phase 9: Benchmarks, Reliability Intelligence, Evidence, and Failure Intelligence."""

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
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BenchmarkSuite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_suites"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class BenchmarkVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_versions"

    benchmark_suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_suites.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(nullable=False)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class BenchmarkRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_benchmark_run_status",
        ),
    )

    benchmark_suite_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_suites.id", ondelete="CASCADE"), index=True, nullable=False
    )
    benchmark_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BenchmarkResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_results"

    benchmark_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    baseline_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.id", ondelete="CASCADE"), nullable=False
    )
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False)


class ReliabilityEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reliability_evidences"

    benchmark_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    benchmark_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("benchmark_results.id", ondelete="CASCADE"), nullable=True
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_value: Mapped[float] = mapped_column(Float, nullable=False)
    absolute_change: Mapped[float] = mapped_column(Float, nullable=False)
    relative_change: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(nullable=False)
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    effect_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    significance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False)


class FailureCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "failure_clusters"

    benchmark_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    benchmark_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("benchmark_results.id", ondelete="CASCADE"), nullable=True
    )
    failure_type: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message_pattern: Mapped[str] = mapped_column(String(1000), nullable=False)
    cluster_count: Mapped[int] = mapped_column(nullable=False)
    cluster_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False)


class RootCauseRecommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "root_cause_recommendations"

    benchmark_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    benchmark_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("benchmark_results.id", ondelete="CASCADE"), nullable=True
    )
    regression_attribution: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    root_cause_analysis: Mapped[str] = mapped_column(String(2000), nullable=False)
    root_cause_confidence: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False)
    recommendation: Mapped[str] = mapped_column(String(2000), nullable=False)
