"""phase7 ci integration and service tokens

Revision ID: 0008_phase7_ci
Revises: 0007_phase6_experiments
Create Date: 2026-08-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_phase7_ci"
down_revision = "0007_phase6_experiments"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Create service_tokens table
    op.create_table(
        "service_tokens",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("token_prefix", sa.String(32), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_service_tokens_token_hash", "service_tokens", ["token_hash"], unique=True)
    op.create_index("ix_service_tokens_project_id", "service_tokens", ["project_id"])
    op.create_index("ix_service_tokens_organization_id", "service_tokens", ["organization_id"])

    # 2. Create ci_runs table
    op.create_table(
        "ci_runs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("experiment_id", _UUID, sa.ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("experiment_run_id", _UUID, sa.ForeignKey("experiment_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("commit_sha", sa.String(255), nullable=False),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("repository", sa.String(255), nullable=False),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("pull_request_url", sa.String(1000), nullable=True),
        sa.Column("ci_provider", sa.String(64), nullable=False),
        sa.Column("ci_run_id", sa.String(255), nullable=False),
        sa.Column("ci_job_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("idempotency_key", sa.String(512), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("idempotency_key", name="uq_ci_run_idempotency_key"),
        sa.CheckConstraint("status IN ('RUNNING','COMPLETED','FAILED','CANCELLED')", name="ck_ci_run_status"),
        sa.CheckConstraint("outcome IN ('PASS','FAIL')", name="ck_ci_run_outcome"),
    )
    op.create_index("ix_ci_runs_project_id", "ci_runs", ["project_id"])


def downgrade() -> None:
    op.drop_table("ci_runs")
    op.drop_table("service_tokens")
