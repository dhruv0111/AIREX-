"""Project and environment models (spec §14–§15, §32–§35)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_project_status"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    application_type: Mapped[str] = mapped_column(String(64), default="generic_llm", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Environment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_environment_project_name"),
        UniqueConstraint("project_id", "environment_type", name="uq_environment_project_type"),
        CheckConstraint(
            "environment_type IN ('DEVELOPMENT','STAGING','PRODUCTION')",
            name="ck_environment_type",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name="ck_environment_status",
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    environment_type: Mapped[str] = mapped_column(String(20), default="DEVELOPMENT", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    default_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL"), nullable=True
    )
    evaluation_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    observability_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_retention_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
