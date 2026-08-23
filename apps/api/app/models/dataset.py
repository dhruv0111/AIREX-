"""Dataset, dataset version and test case models (spec §18–§20; Phase 2 §4–§27).

Phase 2 extends the Phase 0 foundation:
- ``Dataset`` gains ``status`` (ACTIVE/ARCHIVED) and ``metadata``.
- ``DatasetVersion`` gains ``status`` (import lifecycle) and ``format``; the
  ``(dataset_id, version_number)`` unique constraint enforces per-dataset
  sequential versioning and prevents duplicate concurrent versions.
- ``TestCase`` gains ``row_number`` (source ordering for canonicalization and
  export) plus indexes on ``status``/``category``.

Dataset versions and their test cases are IMMUTABLE once created (see
DatasetService): nothing in this module mutates an existing version.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Dataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_dataset_status"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class DatasetVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_no"),
        CheckConstraint(
            "status IN ('UPLOADING','VALIDATING','PROCESSING','COMPLETED','FAILED')",
            name="ck_dataset_version_status",
        ),
        Index("ix_dataset_versions_checksum", "checksum"),
    )

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    format: Mapped[str] = mapped_column(String(10), default="jsonl", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class TestCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','ARCHIVED')",
            name="ck_test_case_status",
        ),
        Index("ix_test_cases_status", "status"),
        Index("ix_test_cases_category", "category"),
    )

    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input: Mapped[str] = mapped_column(String(8000), nullable=False)
    expected_output: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
