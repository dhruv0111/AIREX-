"""Phase 10 Intelligence & Deployment Decision Layer

Revision ID: 0011_phase10_intelligence
Revises: 0010_phase9_benchmarking
Create Date: 2026-08-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_phase10_intelligence"
down_revision = "0010_phase9_benchmarking"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Create release_policies table
    op.create_table(
        "release_policies",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_reliability_score", sa.Float(), nullable=True),
        sa.Column("max_regression_severity", sa.String(50), nullable=True),
        sa.Column("max_error_rate", sa.Float(), nullable=True),
        sa.Column("max_latency_ms", sa.Float(), nullable=True),
        sa.Column("max_p95_latency_ms", sa.Float(), nullable=True),
        sa.Column("max_cost", sa.Float(), nullable=True),
        sa.Column("max_critical_alerts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_statistical_confidence", sa.Float(), nullable=True),
        sa.Column("min_sample_size", sa.Integer(), nullable=True),
        sa.Column("required_benchmark", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("required_evaluation", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("required_dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("required_quality_gates", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_evidence_age_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("custom_rules", sa.JSON(), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_release_policies_project_id", "release_policies", ["project_id"])
    op.create_index("ix_release_policies_environment_id", "release_policies", ["environment_id"])

    # 2. Create release_decisions table
    op.create_table(
        "release_decisions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", _UUID, sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("release_policy_id", _UUID, sa.ForeignKey("release_policies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("model_configuration", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="DRAFT"),
        sa.Column("outcome", sa.String(50), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("readiness_breakdown", sa.JSON(), nullable=True),
        sa.Column("configuration_fingerprint", sa.String(64), nullable=False),
        sa.Column("stale_reason", sa.String(1000), nullable=True),
        sa.Column("superseded_by_id", _UUID, sa.ForeignKey("release_decisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_release_decisions_project_id", "release_decisions", ["project_id"])
    op.create_index("ix_release_decisions_organization_id", "release_decisions", ["organization_id"])
    op.create_index("ix_release_decisions_environment_id", "release_decisions", ["environment_id"])
    op.create_index("ix_release_decisions_model_id", "release_decisions", ["model_id"])
    op.create_index("ix_release_decisions_status", "release_decisions", ["status"])
    op.create_index("ix_release_decisions_created_at", "release_decisions", ["created_at"])

    # 3. Create release_evidences table
    op.create_table(
        "release_evidences",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("release_decision_id", _UUID, sa.ForeignKey("release_decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("methodology_version", sa.String(32), nullable=True),
        sa.Column("freshness_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_fresh", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_release_evidences_decision_id", "release_evidences", ["release_decision_id"])
    op.create_index("ix_release_evidences_source_type", "release_evidences", ["source_type"])

    # 4. Create release_checks table
    op.create_table(
        "release_checks",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("release_decision_id", _UUID, sa.ForeignKey("release_decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("actual_value", sa.JSON(), nullable=True),
        sa.Column("expected_value", sa.JSON(), nullable=True),
        sa.Column("evidence_reference", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.String(2000), nullable=False),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_release_checks_decision_id", "release_checks", ["release_decision_id"])
    op.create_index("ix_release_checks_status", "release_checks", ["status"])


def downgrade() -> None:
    op.drop_table("release_checks")
    op.drop_table("release_evidences")
    op.drop_table("release_decisions")
    op.drop_table("release_policies")
