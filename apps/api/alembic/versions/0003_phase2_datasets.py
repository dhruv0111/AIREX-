"""phase2 dataset versioning: extend datasets/dataset_versions/test_cases

Revision ID: 0003_phase2_datasets
Revises: 0002_phase1
Create Date: 2026-08-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_phase2_datasets"
down_revision = "0002_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- datasets: add status + metadata (Phase 2 lifecycle) ----
    op.add_column(
        "datasets",
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("datasets", sa.Column("metadata", sa.JSON(), nullable=True))
    op.create_check_constraint(
        "ck_dataset_status", "datasets", "status IN ('ACTIVE','ARCHIVED')"
    )

    # ---- dataset_versions: add import status + source format; index checksum ----
    op.add_column(
        "dataset_versions",
        sa.Column("status", sa.String(20), nullable=False, server_default="COMPLETED"),
    )
    op.add_column(
        "dataset_versions",
        sa.Column("format", sa.String(10), nullable=False, server_default="jsonl"),
    )
    op.create_check_constraint(
        "ck_dataset_version_status",
        "dataset_versions",
        "status IN ('UPLOADING','VALIDATING','PROCESSING','COMPLETED','FAILED')",
    )
    op.create_index("ix_dataset_versions_checksum", "dataset_versions", ["checksum"])

    # ---- test_cases: add source row ordering + status/category indexes ----
    op.add_column("test_cases", sa.Column("row_number", sa.Integer(), nullable=True))
    op.create_index("ix_test_cases_status", "test_cases", ["status"])
    op.create_index("ix_test_cases_category", "test_cases", ["category"])


def downgrade() -> None:
    op.drop_index("ix_test_cases_category", table_name="test_cases")
    op.drop_index("ix_test_cases_status", table_name="test_cases")
    op.drop_column("test_cases", "row_number")

    op.drop_index("ix_dataset_versions_checksum", table_name="dataset_versions")
    op.drop_constraint("ck_dataset_version_status", "dataset_versions", type_="check")
    op.drop_column("dataset_versions", "format")
    op.drop_column("dataset_versions", "status")

    op.drop_constraint("ck_dataset_status", "datasets", type_="check")
    op.drop_column("datasets", "metadata")
    op.drop_column("datasets", "status")
