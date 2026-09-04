"""Phase 11 AI Agent Evaluation, Trajectory Testing & Agent Reliability

Revision ID: 0012_phase11_agent_evaluation
Revises: 0011_phase10_intelligence
Create Date: 2026-08-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_phase11_agent_evaluation"
down_revision = "0011_phase10_intelligence"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Create tool_definitions table
    op.create_table(
        "tool_definitions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("safety_level", sa.String(32), default="LOW", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), default=30, nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_definitions_project_id", "tool_definitions", ["project_id"])
    op.create_index("ix_tool_definitions_proj_name_ver", "tool_definitions", ["project_id", "name", "version"], unique=True)

    # 2. Create agent_definitions table
    op.create_table(
        "agent_definitions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("agent_type", sa.String(50), default="TOOL_AGENT", nullable=False),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("provider_id", _UUID, sa.ForeignKey("providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id", ondelete="SET NULL"), nullable=True),
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("tool_manifest", sa.JSON(), nullable=True),
        sa.Column("retrieval_configuration", sa.JSON(), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("configuration_fingerprint", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_definitions_project_id", "agent_definitions", ["project_id"])
    op.create_index("ix_agent_definitions_fingerprint", "agent_definitions", ["configuration_fingerprint"])
    op.create_index("ix_agent_definitions_proj_name_ver", "agent_definitions", ["project_id", "name", "version"], unique=True)

    # 3. Create agent_runs table
    op.create_table(
        "agent_runs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", _UUID, sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_version", sa.Integer(), nullable=False),
        sa.Column("agent_fingerprint", sa.String(64), nullable=False),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("test_case_id", _UUID, sa.ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(50), default="PENDING", nullable=False),
        sa.Column("goal_completion_status", sa.String(50), default="UNKNOWN", nullable=False),
        sa.Column("total_steps", sa.Integer(), default=0, nullable=False),
        sa.Column("total_tool_calls", sa.Integer(), default=0, nullable=False),
        sa.Column("successful_tool_calls", sa.Integer(), default=0, nullable=False),
        sa.Column("failed_tool_calls", sa.Integer(), default=0, nullable=False),
        sa.Column("recovered_failures", sa.Integer(), default=0, nullable=False),
        sa.Column("unrecovered_failures", sa.Integer(), default=0, nullable=False),
        sa.Column("loops_detected", sa.Integer(), default=0, nullable=False),
        sa.Column("safety_violations", sa.Integer(), default=0, nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("final_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("reliability_breakdown", sa.JSON(), nullable=True),
        sa.Column("evaluation_checks", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_trace_id", "agent_runs", ["trace_id"])

    # 4. Create agent_trajectory_steps table
    op.create_table(
        "agent_trajectory_steps",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("agent_run_id", _UUID, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), default="SUCCESS", nullable=False),
        sa.Column("parent_step_id", _UUID, sa.ForeignKey("agent_trajectory_steps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("span_id", sa.String(64), nullable=True),
        sa.Column("tool_definition_id", _UUID, sa.ForeignKey("tool_definitions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("tool_call_id", sa.String(128), nullable=True),
        sa.Column("tool_arguments", sa.JSON(), nullable=True),
        sa.Column("tool_result", sa.JSON(), nullable=True),
        sa.Column("model_input", sa.Text(), nullable=True),
        sa.Column("model_output", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index("ix_agent_trajectory_steps_run_id", "agent_trajectory_steps", ["agent_run_id"])
    op.create_index("ix_agent_trajectory_steps_step_no", "agent_trajectory_steps", ["agent_run_id", "step_number"])
    op.create_index("ix_agent_trajectory_steps_span_id", "agent_trajectory_steps", ["span_id"])


def downgrade() -> None:
    op.drop_table("agent_trajectory_steps")
    op.drop_table("agent_runs")
    op.drop_table("agent_definitions")
    op.drop_table("tool_definitions")
