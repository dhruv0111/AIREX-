"""Phase 9 benchmarking, reliability evidence, failure clustering, and root-cause analysis

Revision ID: 0010_phase9_benchmarking
Revises: 0009_phase8_observability
Create Date: 2026-08-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_phase9_benchmarking"
down_revision = "0009_phase8_observability"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Create benchmark_suites table
    op.create_table(
        "benchmark_suites",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_benchmark_suites_project_id", "benchmark_suites", ["project_id"])

    # 2. Create benchmark_versions table
    op.create_table(
        "benchmark_versions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("benchmark_suite_id", _UUID, sa.ForeignKey("benchmark_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_benchmark_versions_benchmark_suite_id", "benchmark_versions", ["benchmark_suite_id"])
    op.create_index("ix_benchmark_versions_configuration_hash", "benchmark_versions", ["configuration_hash"])

    # 3. Create benchmark_runs table
    op.create_table(
        "benchmark_runs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("benchmark_suite_id", _UUID, sa.ForeignKey("benchmark_suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benchmark_version_id", _UUID, sa.ForeignKey("benchmark_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="QUEUED", nullable=False),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("methodology_version", sa.String(20), server_default="1.0", nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_benchmark_runs_benchmark_suite_id", "benchmark_runs", ["benchmark_suite_id"])

    # 4. Create benchmark_results table
    op.create_table(
        "benchmark_results",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("benchmark_run_id", _UUID, sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluation_run_id", _UUID, sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_run_id", _UUID, sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reliability_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_benchmark_results_benchmark_run_id", "benchmark_results", ["benchmark_run_id"])

    # 5. Create reliability_evidences table
    op.create_table(
        "reliability_evidences",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("benchmark_run_id", _UUID, sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benchmark_result_id", _UUID, sa.ForeignKey("benchmark_results.id", ondelete="CASCADE"), nullable=True),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("candidate_value", sa.Float(), nullable=False),
        sa.Column("absolute_change", sa.Float(), nullable=False),
        sa.Column("relative_change", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("effect_size", sa.Float(), nullable=True),
        sa.Column("confidence_interval_low", sa.Float(), nullable=True),
        sa.Column("confidence_interval_high", sa.Float(), nullable=True),
        sa.Column("significance", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("confidence", sa.String(20), server_default="LOW", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_reliability_evidences_benchmark_run_id", "reliability_evidences", ["benchmark_run_id"])

    # 6. Create failure_clusters table
    op.create_table(
        "failure_clusters",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("benchmark_run_id", _UUID, sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benchmark_result_id", _UUID, sa.ForeignKey("benchmark_results.id", ondelete="CASCADE"), nullable=True),
        sa.Column("failure_type", sa.String(50), nullable=False),
        sa.Column("error_message_pattern", sa.String(1000), nullable=False),
        sa.Column("cluster_count", sa.Integer(), nullable=False),
        sa.Column("cluster_percentage", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(20), server_default="LOW", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_failure_clusters_benchmark_run_id", "failure_clusters", ["benchmark_run_id"])

    # 7. Create root_cause_recommendations table
    op.create_table(
        "root_cause_recommendations",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("benchmark_run_id", _UUID, sa.ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benchmark_result_id", _UUID, sa.ForeignKey("benchmark_results.id", ondelete="CASCADE"), nullable=True),
        sa.Column("regression_attribution", sa.String(1000), nullable=True),
        sa.Column("root_cause_analysis", sa.String(2000), nullable=False),
        sa.Column("root_cause_confidence", sa.String(20), server_default="LOW", nullable=False),
        sa.Column("recommendation", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_root_cause_recommendations_benchmark_run_id", "root_cause_recommendations", ["benchmark_run_id"])


def downgrade() -> None:
    op.drop_table("root_cause_recommendations")
    op.drop_table("failure_clusters")
    op.drop_table("reliability_evidences")
    op.drop_table("benchmark_results")
    op.drop_table("benchmark_runs")
    op.drop_table("benchmark_versions")
    op.drop_table("benchmark_suites")
