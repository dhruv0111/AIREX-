"""SQLAlchemy models for Enterprise Identity Providers & Organization Domains (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class IdentityProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Enterprise Identity Provider configuration (OIDC, OAuth2, SAML2, Mock)."""

    __tablename__ = "identity_providers"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_idp_org_name"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), default="OIDC", nullable=False)  # OIDC, OAUTH2, SAML2, MOCK
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)  # DRAFT, ACTIVE, DISABLED, ERROR

    issuer_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stored encrypted via SecretManager — never returned plaintext
    client_secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    authorization_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    userinfo_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    allowed_domains: Mapped[list[str] | None] = mapped_column(JSON, default=list, nullable=True)
    default_role: Mapped[str] = mapped_column(String(32), default="VIEWER", nullable=False)
    enforce_sso: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    jit_provisioning_policy: Mapped[str] = mapped_column(
        String(64), default="ALLOW_APPROVED_DOMAINS_ONLY", nullable=False
    )  # DISABLED, ALLOW_NEW_USERS, ALLOW_APPROVED_DOMAINS_ONLY, ADMIN_APPROVAL_REQUIRED


class OrganizationDomain(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Verified organization domain for SSO enforcement and JIT user provisioning."""

    __tablename__ = "organization_domains"
    __table_args__ = (
        UniqueConstraint("domain", name="uq_org_domains_domain"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(String(255), index=True, nullable=False)  # e.g., acme.com (lowercase)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)  # PENDING, VERIFIED, FAILED, DISABLED
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[str] = mapped_column(String(128), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(32), default="DNS_TXT", nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
