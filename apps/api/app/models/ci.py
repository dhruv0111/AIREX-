"""CI/CD Integration and Service Token models (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    ForeignKey,
    String,
    DateTime,
    Integer,
    Float,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ServiceToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_tokens"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CIRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ci_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ci_run_idempotency_key"),
        CheckConstraint(
            "status IN ('RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_ci_run_status",
        ),
        CheckConstraint(
            "outcome IN ('PASS','FAIL')",
            name="ck_ci_run_outcome",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    experiment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    experiment_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True
    )
    commit_sha: Mapped[str] = mapped_column(String(255), nullable=False)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    pull_request_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pull_request_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ci_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    ci_run_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ci_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
