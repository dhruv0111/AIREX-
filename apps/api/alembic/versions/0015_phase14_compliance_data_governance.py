"""Phase 14 Compliance, Audit Intelligence & Data Governance

Revision ID: 0015_phase14_compliance_data_governance
Revises: 0014_phase13_identity_collaboration_governance
Create Date: 2026-09-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_phase14_compliance_data_governance"
down_revision = "0014_phase13_identity_collaboration_governance"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Compliance Frameworks
    op.create_table(
        "compliance_frameworks",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("applicability", sa.JSON(), nullable=True),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("is_immutable", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_frameworks_organization_id", "compliance_frameworks", ["organization_id"])

    # 2. Compliance Controls
    op.create_table(
        "compliance_controls",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("framework_id", _UUID, sa.ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), server_default="GOVERNANCE", nullable=False),
        sa.Column("risk_level", sa.String(32), server_default="MEDIUM", nullable=False),
        sa.Column("applicability", sa.JSON(), nullable=True),
        sa.Column("required_evidence_types", sa.JSON(), nullable=True),
        sa.Column("evaluation_frequency", sa.String(32), server_default="CONTINUOUS", nullable=False),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), server_default="NOT_ASSESSED", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_controls_framework_id", "compliance_controls", ["framework_id"])

    # 3. Compliance Evidence
    op.create_table(
        "compliance_evidence",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("sha256_fingerprint", sa.String(64), nullable=False),
        sa.Column("data_classification", sa.String(32), server_default="INTERNAL", nullable=False),
        sa.Column("validity_window_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_status", sa.String(32), server_default="FRESH", nullable=False),
        sa.Column("integrity_status", sa.String(32), server_default="VALID", nullable=False),
        sa.Column("metadata_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_evidence_organization_id", "compliance_evidence", ["organization_id"])
    op.create_index("ix_compliance_evidence_project_id", "compliance_evidence", ["project_id"])
    op.create_index("ix_compliance_evidence_source_type", "compliance_evidence", ["source_type"])
    op.create_index("ix_compliance_evidence_source_id", "compliance_evidence", ["source_id"])

    # 4. Retention Policies
    op.create_table(
        "retention_policies",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_retention_policies_organization_id", "retention_policies", ["organization_id"])
    op.create_index("ix_retention_policies_resource_type", "retention_policies", ["resource_type"])

    # 5. Legal Holds
    op.create_table(
        "legal_holds",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("target_resource_id", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("placed_by_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_legal_holds_organization_id", "legal_holds", ["organization_id"])
    op.create_index("ix_legal_holds_resource_type", "legal_holds", ["resource_type"])
    op.create_index("ix_legal_holds_target_resource_id", "legal_holds", ["target_resource_id"])

    # 6. Compliance Assessments
    op.create_table(
        "compliance_assessments",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("framework_id", _UUID, sa.ForeignKey("compliance_frameworks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("overall_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("assessed_by_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_assessments_organization_id", "compliance_assessments", ["organization_id"])
    op.create_index("ix_compliance_assessments_framework_id", "compliance_assessments", ["framework_id"])

    # 7. Compliance Assessment Items
    op.create_table(
        "compliance_assessment_items",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("assessment_id", _UUID, sa.ForeignKey("compliance_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", _UUID, sa.ForeignKey("compliance_controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), server_default="NOT_ASSESSED", nullable=False),
        sa.Column("evidence_references", sa.JSON(), nullable=True),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_assessment_items_assessment_id", "compliance_assessment_items", ["assessment_id"])
    op.create_index("ix_compliance_assessment_items_control_id", "compliance_assessment_items", ["control_id"])

    # 8. Compliance Remediations
    op.create_table(
        "compliance_remediations",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", _UUID, sa.ForeignKey("compliance_assessments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("control_id", _UUID, sa.ForeignKey("compliance_controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(32), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("owner_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("accepted_risk_justification", sa.Text(), nullable=True),
        sa.Column("accepted_risk_approver_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_risk_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_remediations_organization_id", "compliance_remediations", ["organization_id"])
    op.create_index("ix_compliance_remediations_assessment_id", "compliance_remediations", ["assessment_id"])
    op.create_index("ix_compliance_remediations_control_id", "compliance_remediations", ["control_id"])


def downgrade() -> None:
    op.drop_table("compliance_remediations")
    op.drop_table("compliance_assessment_items")
    op.drop_table("compliance_assessments")
    op.drop_table("legal_holds")
    op.drop_table("retention_policies")
    op.drop_table("compliance_evidence")
    op.drop_table("compliance_controls")
    op.drop_table("compliance_frameworks")
