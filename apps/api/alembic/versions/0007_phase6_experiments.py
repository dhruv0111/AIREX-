"""phase6 experiments, runs, variants, regressions, quality gates

Revision ID: 0007_phase6_experiments
Revises: 0006_phase5_test_generation
Create Date: 2026-08-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_phase6_experiments"
down_revision = "0006_phase5_test_generation"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Alter experiments table
    op.add_column("experiments", sa.Column("experiment_type", sa.String(50), nullable=False, server_default="MODEL_COMPARISON"))
    op.add_column("experiments", sa.Column("fingerprint", sa.String(64), nullable=True))
    op.add_column("experiments", sa.Column("duplicate_of", _UUID, sa.ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True))
    op.add_column("experiments", sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("experiments", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("experiments", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    op.drop_constraint("ck_experiment_status", "experiments", type_="check")
    op.create_check_constraint(
        "ck_experiment_status",
        "experiments",
        "status IN ('DRAFT','QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED','INCONCLUSIVE')",
    )
    op.create_index("ix_experiments_fingerprint", "experiments", ["fingerprint"])

    # 2. Create experiment_variants table
    op.create_table(
        "experiment_variants",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("experiment_id", _UUID, sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_type", sa.String(20), nullable=False),
        sa.Column("model_id", _UUID, sa.ForeignKey("models.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt_version_id", _UUID, sa.ForeignKey("prompt_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.UniqueConstraint("experiment_id", "variant_type", name="uq_experiment_variant_type"),
    )
    op.create_check_constraint(
        "ck_variant_type",
        "experiment_variants",
        "variant_type IN ('BASELINE','CANDIDATE')",
    )
    op.create_index("ix_experiment_variants_experiment_id", "experiment_variants", ["experiment_id"])

    # 3. Create experiment_runs table
    op.create_table(
        "experiment_runs",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("experiment_id", _UUID, sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("baseline_run_id", _UUID, sa.ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("candidate_run_id", _UUID, sa.ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(2000), nullable=True),
    )
    op.create_check_constraint(
        "ck_experiment_run_status",
        "experiment_runs",
        "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
    )
    op.create_index("ix_experiment_runs_experiment_id", "experiment_runs", ["experiment_id"])

    # 4. Create experiment_comparisons table
    op.create_table(
        "experiment_comparisons",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("run_id", _UUID, sa.ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("candidate_value", sa.Float(), nullable=True),
        sa.Column("absolute_difference", sa.Float(), nullable=True),
        sa.Column("relative_difference", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("statistical_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_experiment_comparisons_run_id", "experiment_comparisons", ["run_id"])

    # 5. Create regressions table
    op.create_table(
        "regressions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("comparison_id", _UUID, sa.ForeignKey("experiment_comparisons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("candidate_value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("explanation", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_regressions_comparison_id", "regressions", ["comparison_id"])

    # 6. Create quality_gates table
    op.create_table(
        "quality_gates",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("experiment_id", _UUID, sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("gate_type", sa.String(50), nullable=False, server_default="CANDIDATE_VALUE"),
        sa.Column("operator", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="HIGH"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quality_gates_experiment_id", "quality_gates", ["experiment_id"])

    # 7. Create quality_gate_results table
    op.create_table(
        "quality_gate_results",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("run_id", _UUID, sa.ForeignKey("experiment_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quality_gate_id", _UUID, sa.ForeignKey("quality_gates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quality_gate_results_run_id", "quality_gate_results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_quality_gate_results_run_id", table_name="quality_gate_results")
    op.drop_table("quality_gate_results")

    op.drop_index("ix_quality_gates_experiment_id", table_name="quality_gates")
    op.drop_table("quality_gates")

    op.drop_index("ix_regressions_comparison_id", table_name="regressions")
    op.drop_table("regressions")

    op.drop_index("ix_experiment_comparisons_run_id", table_name="experiment_comparisons")
    op.drop_table("experiment_comparisons")

    op.drop_index("ix_experiment_runs_experiment_id", table_name="experiment_runs")
    op.drop_constraint("ck_experiment_run_status", "experiment_runs", type_="check")
    op.drop_table("experiment_runs")

    op.drop_index("ix_experiment_variants_experiment_id", table_name="experiment_variants")
    op.drop_constraint("ck_variant_type", "experiment_variants", type_="check")
    op.drop_table("experiment_variants")

    op.drop_index("ix_experiments_fingerprint", "experiments")
    op.drop_constraint("ck_experiment_status", "experiments", type_="check")
    op.create_check_constraint(
        "ck_experiment_status",
        "experiments",
        "status IN ('DRAFT','RUNNING','COMPLETED','FAILED')",
    )

    op.drop_column("experiments", "heartbeat_at")
    op.drop_column("experiments", "started_at")
    op.drop_column("experiments", "created_by")
    op.drop_column("experiments", "duplicate_of")
    op.drop_column("experiments", "fingerprint")
    op.drop_column("experiments", "experiment_type")
