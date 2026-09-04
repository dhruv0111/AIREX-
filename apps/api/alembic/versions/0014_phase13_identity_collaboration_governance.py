"""Phase 13 Enterprise Identity, Collaboration & Governance

Revision ID: 0014_phase13_identity_collaboration_governance
Revises: 0013_phase12_production_readiness
Create Date: 2026-09-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_phase13_identity_collaboration_governance"
down_revision = "0013_phase12_production_readiness"
branch_labels = None
depends_on = None

_UUID = sa.Uuid()


def upgrade() -> None:
    # 1. Identity Providers
    op.create_table(
        "identity_providers",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider_type", sa.String(32), server_default="OIDC", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("issuer_url", sa.String(512), nullable=True),
        sa.Column("client_id", sa.String(255), nullable=True),
        sa.Column("client_secret_encrypted", sa.String(1024), nullable=True),
        sa.Column("authorization_endpoint", sa.String(512), nullable=True),
        sa.Column("token_endpoint", sa.String(512), nullable=True),
        sa.Column("userinfo_endpoint", sa.String(512), nullable=True),
        sa.Column("metadata_url", sa.String(512), nullable=True),
        sa.Column("allowed_domains", sa.JSON(), nullable=True),
        sa.Column("default_role", sa.String(32), server_default="VIEWER", nullable=False),
        sa.Column("enforce_sso", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("jit_provisioning_policy", sa.String(64), server_default="ALLOW_APPROVED_DOMAINS_ONLY", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_idp_org_name"),
    )
    op.create_index("ix_identity_providers_organization_id", "identity_providers", ["organization_id"])

    # 2. Organization Domains
    op.create_table(
        "organization_domains",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("verification_token", sa.String(128), nullable=False),
        sa.Column("verification_method", sa.String(32), server_default="DNS_TXT", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("domain", name="uq_org_domains_domain"),
    )
    op.create_index("ix_organization_domains_organization_id", "organization_domains", ["organization_id"])
    op.create_index("ix_organization_domains_domain", "organization_domains", ["domain"])

    # 3. Teams
    op.create_table(
        "teams",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_team_org_slug"),
    )
    op.create_index("ix_teams_organization_id", "teams", ["organization_id"])

    # 4. Team Members
    op.create_table(
        "team_members",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("team_id", _UUID, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), server_default="MEMBER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    # 5. Team Project Access
    op.create_table(
        "team_project_access",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("team_id", _UUID, sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_role", sa.String(32), server_default="ENGINEER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "project_id", name="uq_team_project_access"),
    )
    op.create_index("ix_team_project_access_team_id", "team_project_access", ["team_id"])
    op.create_index("ix_team_project_access_project_id", "team_project_access", ["project_id"])

    # 6. User Project Access
    op.create_table(
        "user_project_access",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("user_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_role", sa.String(32), server_default="ENGINEER", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "project_id", name="uq_user_project_access"),
    )
    op.create_index("ix_user_project_access_user_id", "user_project_access", ["user_id"])
    op.create_index("ix_user_project_access_project_id", "user_project_access", ["project_id"])

    # 7. Governance Policies
    op.create_table(
        "governance_policies",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(32), server_default="DRAFT", nullable=False),
        sa.Column("rules", sa.JSON(), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", "version", name="uq_gov_policy_org_name_ver"),
    )
    op.create_index("ix_governance_policies_organization_id", "governance_policies", ["organization_id"])

    # 8. Approval Requests
    op.create_table(
        "approval_requests",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", _UUID, sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("requester_id", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("required_role", sa.String(32), server_default="ADMIN", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approval_requests_organization_id", "approval_requests", ["organization_id"])
    op.create_index("ix_approval_requests_target_id", "approval_requests", ["target_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    # 9. Approval Steps
    op.create_table(
        "approval_steps",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("request_id", _UUID, sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("approver_role", sa.String(32), server_default="ADMIN", nullable=False),
        sa.Column("status", sa.String(32), server_default="PENDING", nullable=False),
        sa.Column("decision_id", _UUID, nullable=True),
    )
    op.create_index("ix_approval_steps_request_id", "approval_steps", ["request_id"])

    # 10. Approval Decisions
    op.create_table(
        "approval_decisions",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("request_id", _UUID, sa.ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decided_by", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("comments", sa.String(2000), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approval_decisions_request_id", "approval_decisions", ["request_id"])

    # 11. Access Reviews
    op.create_table(
        "access_reviews",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), server_default="OPEN", nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", _UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_access_reviews_organization_id", "access_reviews", ["organization_id"])
    op.create_index("ix_access_reviews_status", "access_reviews", ["status"])

    # 12. Access Review Items
    op.create_table(
        "access_review_items",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("review_id", _UUID, sa.ForeignKey("access_reviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("context_info", sa.JSON(), nullable=True),
        sa.Column("decision", sa.String(32), server_default="NO_ACTION", nullable=False),
        sa.Column("decided_by", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
    )
    op.create_index("ix_access_review_items_review_id", "access_review_items", ["review_id"])
    op.create_index("ix_access_review_items_subject_id", "access_review_items", ["subject_id"])


def downgrade() -> None:
    op.drop_table("access_review_items")
    op.drop_table("access_reviews")
    op.drop_table("approval_decisions")
    op.drop_table("approval_steps")
    op.drop_table("approval_requests")
    op.drop_table("governance_policies")
    op.drop_table("user_project_access")
    op.drop_table("team_project_access")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("organization_domains")
    op.drop_table("identity_providers")
