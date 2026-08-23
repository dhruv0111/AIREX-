"""Rubric model (Phase 4 §20–§21).

A rubric row is a single immutable version of a scoring rubric. The version
family is identified by ``(project_id, name)``; editing is expressed by creating
a new version (the previous ACTIVE version is archived). Once a version has been
referenced by an evaluation run it can never be mutated (see
``app/services/rubric.py`` and ADR-019).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Rubric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rubrics"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_rubric_status"),
        Index("ix_rubrics_project_name", "project_id", "name"),
        Index("ix_rubrics_project_status", "project_id", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Sequential per (project_id, name): 1, 2, 3, ...
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # Normalized criteria list: [{name, description, weight, min_score, max_score}]
    criteria: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
