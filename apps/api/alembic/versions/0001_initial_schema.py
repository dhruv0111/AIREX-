"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ---- organizations ----
    op.create_table(
        "organizations",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # ---- organization_members ----
    op.create_table(
        "organization_members",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
        sa.CheckConstraint("role IN ('OWNER','ADMIN','ENGINEER','VIEWER')", name="ck_org_member_role"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    # ---- projects ----
    op.create_table(
        "projects",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("application_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="ck_project_status"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    # ---- environments ----
    op.create_table(
        "environments",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("environment_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_environment_project_name"),
        sa.CheckConstraint("environment_type IN ('DEVELOPMENT','STAGING','PRODUCTION')", name="ck_environment_type"),
    )
    op.create_index("ix_environments_project_id", "environments", ["project_id"])

    # ---- providers ----
    op.create_table(
        "providers",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("encrypted_credentials", sa.String(2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider_type IN ('OPENAI','ANTHROPIC','GOOGLE','CUSTOM','LOCAL')", name="ck_provider_type"),
    )
    op.create_index("ix_providers_organization_id", "providers", ["organization_id"])

    # ---- models ----
    op.create_table(
        "models",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", _UUID, sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("model_identifier", sa.String(255), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_models_project_id", "models", ["project_id"])

    # ---- datasets ----
    op.create_table(
        "datasets",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    # ---- dataset_versions ----
    op.create_table(
        "dataset_versions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("dataset_id", _UUID, sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_reference", sa.String(500), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_no"),
    )
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])

    # ---- test_cases ----
    op.create_table(
        "test_cases",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("input", sa.String(8000), nullable=False),
        sa.Column("expected_output", sa.String(8000), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("difficulty", sa.String(32), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','ARCHIVED')", name="ck_test_case_status"),
    )
    op.create_index("ix_test_cases_dataset_version_id", "test_cases", ["dataset_version_id"])

    # ---- evaluation_runs ----
    op.create_table(
        "evaluation_runs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id"), nullable=True),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')", name="ck_evaluation_run_status"),
    )
    op.create_index("ix_evaluation_runs_project_id", "evaluation_runs", ["project_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])

    # ---- evaluation_results ----
    op.create_table(
        "evaluation_results",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("evaluation_run_id", _UUID, sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_case_id", _UUID, sa.ForeignKey("test_cases.id"), nullable=True),
        sa.Column("actual_output", sa.String(8000), nullable=True),
        sa.Column("score", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_type", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 8), nullable=True),
        sa.Column("explanation", sa.String(4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('PASS','FAIL','WARNING','ERROR','PENDING')", name="ck_evaluation_result_status"),
    )
    op.create_index("ix_evaluation_results_evaluation_run_id", "evaluation_results", ["evaluation_run_id"])

    # ---- experiments ----
    op.create_table(
        "experiments",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id"), nullable=True),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id"), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','RUNNING','COMPLETED','FAILED')", name="ck_experiment_status"),
    )
    op.create_index("ix_experiments_project_id", "experiments", ["project_id"])

    # ---- prompts ----
    op.create_table(
        "prompts",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prompts_project_id", "prompts", ["project_id"])

    # ---- prompt_versions ----
    op.create_table(
        "prompt_versions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("prompt_id", _UUID, sa.ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(16000), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("prompt_id", "version_number", name="uq_prompt_version_no"),
    )
    op.create_index("ix_prompt_versions_prompt_id", "prompt_versions", ["prompt_id"])

    # ---- traces ----
    op.create_table(
        "traces",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id"), nullable=True),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trace_id", name="uq_traces_trace_id"),
    )
    op.create_index("ix_traces_project_id", "traces", ["project_id"])
    op.create_index("ix_traces_trace_id", "traces", ["trace_id"])

    # ---- trace_events ----
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
    op.create_index("ix_trace_events_trace_id", "trace_events", ["trace_id"])

    # ---- alert_rules ----
    op.create_table(
        "alert_rules",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(8), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 6), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="WARNING"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_rules_project_id", "alert_rules", ["project_id"])

    # ---- alerts ----
    op.create_table(
        "alerts",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("alert_rule_id", _UUID, sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="FIRING"),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.String(2000), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_alert_rule_id", "alerts", ["alert_rule_id"])
    op.create_index("ix_alerts_project_id", "alerts", ["project_id"])

    # ---- audit_logs ----
    op.create_table(
        "audit_logs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", _UUID, nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
    op.drop_table("trace_events")
    op.drop_table("traces")
    op.drop_table("prompt_versions")
    op.drop_table("prompts")
    op.drop_table("experiments")
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("test_cases")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
    op.drop_table("models")
    op.drop_table("providers")
    op.drop_table("environments")
    op.drop_table("projects")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_table("users")
