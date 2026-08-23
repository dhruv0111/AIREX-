"""Test-generation request and generated-candidate models (Phase 5).

Generated test cases are never automatically trusted: candidates start as
PENDING_REVIEW and only APPROVED candidates can enter a dataset version (ADR-022).
Fingerprints (SHA-256 over normalized content) make generation idempotent and
deduplication deterministic (ADR-021/ADR-023).
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
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GenerationRequest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generation_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_generation_request_status",
        ),
        CheckConstraint(
            "source_type IN ('MANUAL_INSTRUCTION','DATASET','TEST_CASES','EVALUATION_FAILURES')",
            name="ck_generation_source_type",
        ),
        Index("ix_generation_requests_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # {"dataset_id","dataset_version_id","dataset_checksum"} or {"evaluation_run_id"}.
    source_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    instruction: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", nullable=False, index=True)
    generator_model_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GeneratedCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_candidates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_REVIEW','APPROVED','REJECTED')",
            name="ck_generation_candidate_status",
        ),
        Index("ix_generation_candidates_request", "generation_request_id"),
        Index("ix_generation_candidates_status", "status"),
        Index("ix_generation_candidates_category", "category"),
    )

    generation_request_id: Mapped[UUID] = mapped_column(
        ForeignKey("generation_requests.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input: Mapped[str] = mapped_column(String(8000), nullable=False)
    expected_output: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW", nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Deterministic SHA-256 fingerprint of normalized content (dedup/idempotency).
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duplicate_of: Mapped[UUID | None] = mapped_column(
        ForeignKey("generation_candidates.id"), nullable=True
    )
    # Consumption tracking: which dataset version included this approved candidate.
    dataset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
