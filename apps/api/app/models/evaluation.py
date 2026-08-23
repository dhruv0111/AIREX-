"""Evaluation run and result models (Phase 0 §19–§20; Phase 3 §6–§10, §45;
Phase 4 §38, §57).

Phase 3 extends the Phase 0 tables with environment/scoping fields, per-run
progress counters, reproducibility snapshots (model config, dataset checksum,
evaluator versions), a heartbeat for stale-run recovery, and an idempotency
unique constraint on (evaluation_run_id, test_case_id). Phase 4 adds LLM-judge
snapshots on the run and judge score fields on each result.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_evaluation_run_status",
        ),
        Index("ix_evaluation_runs_dataset_version_id", "dataset_version_id"),
        Index("ix_evaluation_runs_model_id", "model_id"),
        Index("ix_evaluation_runs_created_at", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    dataset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    model_id: Mapped[UUID | None] = mapped_column(ForeignKey("models.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True, nullable=False)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Reproducibility snapshots (immutable once set at creation).
    model_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dataset_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evaluator_versions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Phase 4 — LLM judge references + frozen snapshots (ADR-020).
    judge_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("models.id"), nullable=True)
    judge_rubric_id: Mapped[UUID | None] = mapped_column(ForeignKey("rubrics.id"), nullable=True)
    judge_model_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_rubric_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvaluationResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PASS','FAIL','ERROR','SKIPPED')",
            name="ck_evaluation_result_status",
        ),
        UniqueConstraint("evaluation_run_id", "test_case_id", name="uq_evaluation_run_case"),
        Index("ix_evaluation_results_status", "status"),
        Index("ix_evaluation_results_failure_type", "failure_type"),
        Index("ix_evaluation_results_test_case_id", "test_case_id"),
    )

    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    test_case_id: Mapped[UUID | None] = mapped_column(ForeignKey("test_cases.id"), nullable=True)
    actual_output: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    score: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    explanation: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    # Phase 4 — LLM judge result fields (spec §38). Combined score reflects the
    # configured pass policy (ANY/ALL/WEIGHTED, §41).
    judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_reasoning: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    judge_criteria_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_model_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_rubric_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    combined_score: Mapped[float | None] = mapped_column(Float, nullable=True)
