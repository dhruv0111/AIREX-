"""SQLAlchemy models for Organization Teams and Granular Project Access (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Organization-level collaborative team."""

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_team_org_slug"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    members: Mapped[list[TeamMember]] = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan", lazy="selectin")
    project_access: Mapped[list[TeamProjectAccess]] = relationship("TeamProjectAccess", back_populates="team", cascade="all, delete-orphan", lazy="selectin")


class TeamMember(UUIDPrimaryKeyMixin, Base):
    """Team membership."""

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), default="MEMBER", nullable=False)  # LEAD, MEMBER
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    team: Mapped[Team] = relationship("Team", back_populates="members")


class TeamProjectAccess(UUIDPrimaryKeyMixin, Base):
    """Project access granted via team membership."""

    __tablename__ = "team_project_access"
    __table_args__ = (
        UniqueConstraint("team_id", "project_id", name="uq_team_project_access"),
    )

    team_id: Mapped[UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission_role: Mapped[str] = mapped_column(String(32), default="ENGINEER", nullable=False)  # VIEWER, ENGINEER, ADMIN
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    team: Mapped[Team] = relationship("Team", back_populates="project_access")


class UserProjectAccess(UUIDPrimaryKeyMixin, Base):
    """Direct project access granted directly to an individual user."""

    __tablename__ = "user_project_access"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project_access"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    permission_role: Mapped[str] = mapped_column(String(32), default="ENGINEER", nullable=False)  # VIEWER, ENGINEER, ADMIN
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
