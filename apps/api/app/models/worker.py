"""Worker reliability models: heartbeat monitoring and dead-letter failure log (spec §42, Phase 12)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class WorkerHeartbeat(UUIDPrimaryKeyMixin, Base):
    """Tracks active background worker processes and their health heartbeats."""

    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, DRAINING, STOPPED, STALE
    active_jobs_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaskFailure(UUIDPrimaryKeyMixin, Base):
    """Dead-letter / failure audit log preventing silent background task loss."""

    __tablename__ = "task_failures"

    job_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(String(2000), nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
