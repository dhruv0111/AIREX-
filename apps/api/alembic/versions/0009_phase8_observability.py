"""Phase 8 production observability, spans, pricing, and incident alert rules

Revision ID: 0009_phase8_observability
Revises: 0008_phase7_ci
Create Date: 2026-08-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_phase8_observability"
down_revision = "0008_phase7_ci"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Drop old trace_events table
    op.execute("DROP TABLE IF EXISTS trace_events")

    # 2. Create spans table
    op.create_table(
        "spans",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("span_id", sa.String(64), nullable=False),
        sa.Column("parent_span_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("span_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="SUCCESS", nullable=False),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_span_id", "spans", ["span_id"])

    # 3. Create model_pricings table
    op.create_table(
        "model_pricings",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("model_pattern", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("input_price_per_1k", sa.Numeric(18, 6), nullable=False),
        sa.Column("output_price_per_1k", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(8), server_default="USD", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_model_pricings_model_pattern", "model_pricings", ["model_pattern"], unique=True)
    op.create_index("ix_model_pricings_provider", "model_pricings", ["provider"])

    # 4. Modify traces table: Add new columns (no explicit FK constraint to avoid SQLite ALTER error)
    op.add_column("traces", sa.Column("organization_id", _UUID, nullable=True))
    op.add_column("traces", sa.Column("environment", sa.String(64), server_default="production", nullable=False))
    op.add_column("traces", sa.Column("service_name", sa.String(255), nullable=True))
    op.add_column("traces", sa.Column("operation_name", sa.String(255), nullable=True))
    op.add_column("traces", sa.Column("duration_ms", sa.Float(), nullable=True))
    op.add_column("traces", sa.Column("error", sa.String(1000), nullable=True))
    op.add_column("traces", sa.Column("user_id", sa.String(255), nullable=True))
    op.add_column("traces", sa.Column("session_id", sa.String(255), nullable=True))
    op.add_column("traces", sa.Column("deployment_version", sa.String(255), nullable=True))
    op.add_column("traces", sa.Column("git_commit", sa.String(255), nullable=True))
    op.add_column("traces", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column("traces", sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("traces", sa.Column("end_time", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_traces_organization_id", "traces", ["organization_id"])
    op.create_index("ix_traces_environment", "traces", ["environment"])

    # 5. Modify alert_rules table: Add environment and cooldown columns
    op.add_column("alert_rules", sa.Column("environment", sa.String(64), nullable=True))
    op.add_column("alert_rules", sa.Column("cooldown_seconds", sa.Integer(), server_default="3600", nullable=False))
    op.add_column("projects", sa.Column("settings", sa.JSON(), nullable=True))

    # 6. Recreate alerts table
    op.execute("DROP TABLE IF EXISTS alerts")
    op.create_table(
        "alerts",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("alert_rule_id", _UUID, sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), server_default="TRIGGERED", nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(2000), nullable=True),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notification_status", sa.String(32), nullable=True),
        sa.Column("notification_error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_alerts_alert_rule_id", "alerts", ["alert_rule_id"])
    op.create_index("ix_alerts_project_id", "alerts", ["project_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alerts")
    # Restore original alerts structure
    op.create_table(
        "alerts",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("alert_rule_id", _UUID, sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="FIRING", nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(2000), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_column("projects", "settings")
    op.drop_column("alert_rules", "cooldown_seconds")
    op.drop_column("alert_rules", "environment")
    op.drop_column("traces", "end_time")
    op.drop_column("traces", "start_time")
    op.drop_column("traces", "quality_score")
    op.drop_column("traces", "git_commit")
    op.drop_column("traces", "deployment_version")
    op.drop_column("traces", "session_id")
    op.drop_column("traces", "user_id")
    op.drop_column("traces", "error")
    op.drop_column("traces", "duration_ms")
    op.drop_column("traces", "operation_name")
    op.drop_column("traces", "service_name")
    op.drop_column("traces", "environment")
    op.drop_column("traces", "organization_id")
    op.drop_table("model_pricings")
    op.drop_table("spans")
    # Restore original empty trace_events table
    op.create_table(
        "trace_events",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("trace_id", _UUID, sa.ForeignKey("traces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trace_id", "sequence_number", name="uq_trace_event_seq"),
    )
