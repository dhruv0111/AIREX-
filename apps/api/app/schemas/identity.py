"""Pydantic schemas for Identity Providers, Domains, and SSO (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class IdentityProviderCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    provider_type: str = Field(default="OIDC")  # OIDC, OAUTH2, SAML2, MOCK
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    allowed_domains: list[str] = Field(default_factory=list)
    default_role: str = Field(default="VIEWER")
    enforce_sso: bool = False
    jit_provisioning_policy: str = Field(default="ALLOW_APPROVED_DOMAINS_ONLY")


class IdentityProviderUpdate(BaseModel):
    name: str | None = None
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    allowed_domains: list[str] | None = None
    default_role: str | None = None
    enforce_sso: bool | None = None
    jit_provisioning_policy: str | None = None
    status: str | None = None


class IdentityProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    provider_type: str
    status: str
    issuer_url: str | None = None
    client_id: str | None = None
    masked_client_secret: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    allowed_domains: list[str] | None = None
    default_role: str
    enforce_sso: bool
    jit_provisioning_policy: str
    created_at: datetime
    updated_at: datetime


class DomainCreate(BaseModel):
    domain: str = Field(..., min_length=3, max_length=255)
    verification_method: str = Field(default="DNS_TXT")


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    domain: str
    status: str
    is_primary: bool
    verification_token: str
    verification_method: str
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SSOInitiateRequest(BaseModel):
    email: str | None = None
    domain: str | None = None


class SSOInitiateResponse(BaseModel):
    idp_id: UUID
    provider_type: str
    authorization_url: str


class SSOCallbackRequest(BaseModel):
    code: str | None = None
    state: str | None = None
    # For mock identity provider testing
    mock_email: str | None = None
    mock_name: str | None = None
