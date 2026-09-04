"""Phase 12 Production Deployment, Enterprise Security & Platform Readiness

Revision ID: 0013_phase12_production_readiness
Revises: 0012_phase11_agent_evaluation
Create Date: 2026-08-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_phase12_production_readiness"
down_revision = "0012_phase11_agent_evaluation"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Add is_superuser column to users
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )

    # 2. Create user_sessions table
    op.create_table(
        "user_sessions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_refresh_token_hash", "user_sessions", ["refresh_token_hash"])

    # 3. Create worker_heartbeats table
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("worker_id", sa.String(128), unique=True, nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), server_default="ACTIVE", nullable=False),
        sa.Column("active_jobs_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worker_heartbeats_worker_id", "worker_heartbeats", ["worker_id"])

    # 4. Create task_failures table (dead-letter queue log)
    op.create_table(
        "task_failures",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("job_id", sa.String(128), nullable=False),
        sa.Column("task_name", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_failures_job_id", "task_failures", ["job_id"])
    op.create_index("ix_task_failures_task_name", "task_failures", ["task_name"])


def downgrade() -> None:
    op.drop_index("ix_task_failures_task_name", table_name="task_failures")
    op.drop_index("ix_task_failures_job_id", table_name="task_failures")
    op.drop_table("task_failures")

    op.drop_index("ix_worker_heartbeats_worker_id", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")

    op.drop_index("ix_user_sessions_refresh_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_superuser")
