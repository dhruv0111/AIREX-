"""phase5 ai test generation: generation_requests + generation_candidates

Revision ID: 0006_phase5_test_generation
Revises: 0005_phase4_llm_judge
Create Date: 2026-08-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_phase5_test_generation"
down_revision = "0005_phase4_llm_judge"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    op.create_table(
        "generation_requests",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column(
            "project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "environment_id", _UUID, sa.ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.JSON(), nullable=True),
        sa.Column("generation_type", sa.String(32), nullable=False),
        sa.Column("instruction", sa.String(4000), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("generator_model_snapshot", sa.JSON(), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_generation_request_status",
        "generation_requests",
        "status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')",
    )
    op.create_check_constraint(
        "ck_generation_source_type",
        "generation_requests",
        "source_type IN ('MANUAL_INSTRUCTION','DATASET','TEST_CASES','EVALUATION_FAILURES')",
    )
    op.create_index(
        "ix_generation_requests_project_created", "generation_requests", ["project_id", "created_at"]
    )

    op.create_table(
        "generation_candidates",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column(
            "generation_request_id",
            _UUID,
            sa.ForeignKey("generation_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("input", sa.String(8000), nullable=False),
        sa.Column("expected_output", sa.String(8000), nullable=True),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("generation_type", sa.String(32), nullable=False),
        sa.Column("difficulty", sa.String(16), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("duplicate_of", _UUID, sa.ForeignKey("generation_candidates.id"), nullable=True),
        sa.Column("dataset_version_id", _UUID, sa.ForeignKey("dataset_versions.id"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_generation_candidate_status",
        "generation_candidates",
        "status IN ('PENDING_REVIEW','APPROVED','REJECTED')",
    )
    op.create_index(
        "ix_generation_candidates_request", "generation_candidates", ["generation_request_id"]
    )
    op.create_index("ix_generation_candidates_status", "generation_candidates", ["status"])
    op.create_index("ix_generation_candidates_category", "generation_candidates", ["category"])


def downgrade() -> None:
    op.drop_index("ix_generation_candidates_category", table_name="generation_candidates")
    op.drop_index("ix_generation_candidates_status", table_name="generation_candidates")
    op.drop_index("ix_generation_candidates_request", table_name="generation_candidates")
    op.drop_constraint("ck_generation_candidate_status", "generation_candidates", type_="check")
    op.drop_table("generation_candidates")

    op.drop_index("ix_generation_requests_project_created", table_name="generation_requests")
    op.drop_constraint("ck_generation_source_type", "generation_requests", type_="check")
    op.drop_constraint("ck_generation_request_status", "generation_requests", type_="check")
    op.drop_table("generation_requests")
