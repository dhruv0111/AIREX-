"""phase1 models/providers/environments

Revision ID: 0002_phase1
Revises: 0001_initial_schema
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_phase1"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # ---- providers: status + credential metadata ----
    op.add_column("providers", sa.Column("credential_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("providers", sa.Column("metadata", sa.JSON(), nullable=True))
    op.add_column("providers", sa.Column("base_url", sa.String(500), nullable=True))
    op.add_column("providers", sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"))
    op.add_column("providers", sa.Column("last_connection_status", sa.String(32), nullable=True))
    op.add_column("providers", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("providers", sa.Column("last_error", sa.String(1000), nullable=True))

    # ---- environments: status + configuration + unique type ----
    op.add_column("environments", sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"))
    op.add_column("environments", sa.Column("default_model_id", _UUID, nullable=True))
    op.add_column("environments", sa.Column("evaluation_policy", sa.JSON(), nullable=True))
    op.add_column("environments", sa.Column("observability_policy", sa.JSON(), nullable=True))
    op.add_column("environments", sa.Column("data_retention_policy", sa.JSON(), nullable=True))

    # ---- models: environment ref + health metadata ----
    op.add_column("models", sa.Column("environment_id", _UUID, nullable=True))
    op.add_column("models", sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"))
    op.add_column("models", sa.Column("last_health_status", sa.String(32), nullable=True))
    op.add_column("models", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("models", sa.Column("last_latency_ms", sa.Integer(), nullable=True))

    # ---- model_invocations (request metadata capture, spec §29) ----
    op.create_table(
        "model_invocations",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_invocations_request_id", "model_invocations", ["request_id"])
    op.create_index("ix_model_invocations_organization_id", "model_invocations", ["organization_id"])
    op.create_index("ix_model_invocations_project_id", "model_invocations", ["project_id"])
    op.create_index("ix_model_invocations_created_at", "model_invocations", ["created_at"])

    # ---- constraints (Postgres) ----
    op.create_check_constraint("ck_provider_status", "providers", "status IN ('ACTIVE','INACTIVE','ERROR')")
    op.create_check_constraint("ck_model_status", "models", "status IN ('ACTIVE','INACTIVE','ERROR')")
    op.create_check_constraint(
        "ck_environment_status", "environments", "status IN ('ACTIVE','INACTIVE')"
    )
    op.create_unique_constraint(
        "uq_environment_project_type", "environments", ["project_id", "environment_type"]
    )
    op.create_foreign_key(
        "fk_environments_default_model", "environments", "models", ["default_model_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_models_environment", "models", "environments", ["environment_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_models_environment", "models", type_="foreignkey")
    op.drop_constraint("fk_environments_default_model", "environments", type_="foreignkey")
    op.drop_constraint("uq_environment_project_type", "environments", type_="unique")
    op.drop_constraint("ck_environment_status", "environments", type_="check")
    op.drop_constraint("ck_model_status", "models", type_="check")
    op.drop_constraint("ck_provider_status", "providers", type_="check")

    op.drop_index("ix_model_invocations_created_at", table_name="model_invocations")
    op.drop_index("ix_model_invocations_project_id", table_name="model_invocations")
    op.drop_index("ix_model_invocations_organization_id", table_name="model_invocations")
    op.drop_index("ix_model_invocations_request_id", table_name="model_invocations")
    op.drop_table("model_invocations")

    op.drop_column("models", "last_latency_ms")
    op.drop_column("models", "last_checked_at")
    op.drop_column("models", "last_health_status")
    op.drop_column("models", "status")
    op.drop_column("models", "environment_id")

    op.drop_column("environments", "data_retention_policy")
    op.drop_column("environments", "observability_policy")
    op.drop_column("environments", "evaluation_policy")
    op.drop_column("environments", "default_model_id")
    op.drop_column("environments", "status")

    op.drop_column("providers", "last_error")
    op.drop_column("providers", "last_checked_at")
    op.drop_column("providers", "last_connection_status")
    op.drop_column("providers", "status")
    op.drop_column("providers", "base_url")
    op.drop_column("providers", "metadata")
    op.drop_column("providers", "credential_version")
