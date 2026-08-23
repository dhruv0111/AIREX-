"""Trace and trace event models (spec §24–§25)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class Trace(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "traces"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trace_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id"), nullable=True
    )
    model_id: Mapped[UUID | None] = mapped_column(ForeignKey("models.id"), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TraceEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "trace_events"
    __table_args__ = (UniqueConstraint("trace_id", "sequence_number", name="uq_trace_event_seq"),)

    trace_id: Mapped[UUID] = mapped_column(
        ForeignKey("traces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
