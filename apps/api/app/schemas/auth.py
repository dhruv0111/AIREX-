"""Authentication schemas (spec §33)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        # AT-004/AT-007: basic strength guard; hashing is done in the service.
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


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
    created_at: datetime


class OrganizationMembership(BaseModel):
    organization_id: UUID
    role: str


class MeResponse(BaseModel):
    user: UserResponse
    memberships: list[OrganizationMembership]
