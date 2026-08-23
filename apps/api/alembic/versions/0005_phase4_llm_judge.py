"""phase4 llm judge: rubrics table + judge fields on evaluation_runs/results

Revision ID: 0005_phase4_llm_judge
Revises: 0004_phase3_evaluation
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_phase4_llm_judge"
down_revision = "0004_phase3_evaluation"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # ---- rubrics (Phase 4 §20) ----
    op.create_table(
        "rubrics",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column(
            "project_id",
            _UUID,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("criteria", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint("ck_rubric_status", "rubrics", "status IN ('ACTIVE','ARCHIVED')")
    op.create_index("ix_rubrics_project_name", "rubrics", ["project_id", "name"])
    op.create_index("ix_rubrics_project_status", "rubrics", ["project_id", "status"])

    # ---- evaluation_runs: judge references + frozen snapshots (ADR-020) ----
    op.add_column(
        "evaluation_runs",
        sa.Column("judge_model_id", _UUID, sa.ForeignKey("models.id"), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("judge_rubric_id", _UUID, sa.ForeignKey("rubrics.id"), nullable=True),
    )
    op.add_column("evaluation_runs", sa.Column("judge_model_snapshot", sa.JSON(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("judge_rubric_snapshot", sa.JSON(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("judge_prompt_version", sa.String(64), nullable=True))

    # ---- evaluation_results: judge score fields (spec §38) ----
    op.add_column("evaluation_results", sa.Column("judge_score", sa.Float(), nullable=True))
    op.add_column("evaluation_results", sa.Column("judge_confidence", sa.Float(), nullable=True))
    op.add_column("evaluation_results", sa.Column("judge_reasoning", sa.String(4000), nullable=True))
    op.add_column("evaluation_results", sa.Column("judge_criteria_scores", sa.JSON(), nullable=True))
    op.add_column("evaluation_results", sa.Column("judge_model_snapshot", sa.JSON(), nullable=True))
    op.add_column("evaluation_results", sa.Column("judge_rubric_snapshot", sa.JSON(), nullable=True))
    op.add_column("evaluation_results", sa.Column("judge_prompt_version", sa.String(64), nullable=True))
    op.add_column("evaluation_results", sa.Column("combined_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluation_results", "combined_score")
    op.drop_column("evaluation_results", "judge_prompt_version")
    op.drop_column("evaluation_results", "judge_rubric_snapshot")
    op.drop_column("evaluation_results", "judge_model_snapshot")
    op.drop_column("evaluation_results", "judge_criteria_scores")
    op.drop_column("evaluation_results", "judge_reasoning")
    op.drop_column("evaluation_results", "judge_confidence")
    op.drop_column("evaluation_results", "judge_score")

    op.drop_column("evaluation_runs", "judge_prompt_version")
    op.drop_column("evaluation_runs", "judge_rubric_snapshot")
    op.drop_column("evaluation_runs", "judge_model_snapshot")
    op.drop_column("evaluation_runs", "judge_rubric_id")
    op.drop_column("evaluation_runs", "judge_model_id")

    op.drop_index("ix_rubrics_project_status", table_name="rubrics")
    op.drop_index("ix_rubrics_project_name", table_name="rubrics")
    op.drop_constraint("ck_rubric_status", "rubrics", type_="check")
    op.drop_table("rubrics")
