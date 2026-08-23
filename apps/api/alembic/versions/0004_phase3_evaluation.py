"""phase3 evaluation engine: extend evaluation_runs/evaluation_results

Revision ID: 0004_phase3_evaluation
Revises: 0003_phase2_datasets
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_phase3_evaluation"
down_revision = "0003_phase2_datasets"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # ---- evaluation_runs: scoping, progress, snapshots, heartbeat, indexes ----
    op.add_column(
        "evaluation_runs",
        sa.Column("environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("completed_tests", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("error_tests", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("evaluation_runs", sa.Column("metrics", sa.JSON(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("model_config", sa.JSON(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("dataset_checksum", sa.String(128), nullable=True))
    op.add_column("evaluation_runs", sa.Column("evaluator_versions", sa.JSON(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "evaluation_runs",
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "ix_evaluation_runs_dataset_version_id", "evaluation_runs", ["dataset_version_id"]
    )
    op.create_index("ix_evaluation_runs_model_id", "evaluation_runs", ["model_id"])
    op.create_index("ix_evaluation_runs_created_at", "evaluation_runs", ["created_at"])

    # ---- evaluation_results: status contract, failure_message, idempotency, indexes ----
    op.drop_constraint("ck_evaluation_result_status", "evaluation_results", type_="check")
    op.create_check_constraint(
        "ck_evaluation_result_status",
        "evaluation_results",
        "status IN ('PASS','FAIL','ERROR','SKIPPED')",
    )
    op.add_column("evaluation_results", sa.Column("failure_message", sa.String(4000), nullable=True))
    op.create_unique_constraint(
        "uq_evaluation_run_case", "evaluation_results", ["evaluation_run_id", "test_case_id"]
    )
    op.create_index("ix_evaluation_results_status", "evaluation_results", ["status"])
    op.create_index("ix_evaluation_results_failure_type", "evaluation_results", ["failure_type"])
    op.create_index("ix_evaluation_results_test_case_id", "evaluation_results", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_results_test_case_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_failure_type", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_status", table_name="evaluation_results")
    op.drop_constraint("uq_evaluation_run_case", "evaluation_results", type_="unique")
    op.drop_column("evaluation_results", "failure_message")
    op.drop_constraint("ck_evaluation_result_status", "evaluation_results", type_="check")
    op.create_check_constraint(
        "ck_evaluation_result_status",
        "evaluation_results",
        "status IN ('PASS','FAIL','WARNING','ERROR','PENDING')",
    )

    op.drop_index("ix_evaluation_runs_created_at", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_model_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_dataset_version_id", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "created_by")
    op.drop_column("evaluation_runs", "heartbeat_at")
    op.drop_column("evaluation_runs", "evaluator_versions")
    op.drop_column("evaluation_runs", "dataset_checksum")
    op.drop_column("evaluation_runs", "model_config")
    op.drop_column("evaluation_runs", "metrics")
    op.drop_column("evaluation_runs", "error_tests")
    op.drop_column("evaluation_runs", "completed_tests")
    op.drop_column("evaluation_runs", "environment_id")
