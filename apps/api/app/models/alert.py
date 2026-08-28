"""Alert rule and alert models (spec §26–§27, Phase 8)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Float,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AlertRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alert_rules"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False) # e.g. error_rate, latency_p95, cost, token_usage, request_rate, quality_score
    operator: Mapped[str] = mapped_column(String(8), nullable=False) # >, <, >=, <=, ==
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="WARNING", nullable=False) # INFO, LOW, MEDIUM, HIGH, CRITICAL
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True) # filters rules to specific environment
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Alert(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alerts"

    alert_rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="TRIGGERED", nullable=False) # NORMAL, TRIGGERED, ACKNOWLEDGED, RESOLVED
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    notification_status: Mapped[str | None] = mapped_column(String(32), nullable=True) # PENDING, SENT, FAILED
    notification_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
