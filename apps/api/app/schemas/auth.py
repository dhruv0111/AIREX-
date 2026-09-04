"""Authentication schemas (spec §33, Phase 12)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        # AT-004/AT-007 / Phase 12: strong password guard
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    is_active: bool
    email_verified: bool
    is_superuser: bool = False
    created_at: datetime


class OrganizationMembership(BaseModel):
    organization_id: UUID
    role: str


class MeResponse(BaseModel):
    user: UserResponse
    memberships: list[OrganizationMembership]


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_info: str | None = None
    ip_address: str | None = None
    is_revoked: bool
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime
