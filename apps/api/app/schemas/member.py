"""Organization member schemas (spec §36–§38)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.permissions import Role

ROLES = tuple(r.value for r in Role)


class MemberAddRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="VIEWER", max_length=20)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return upper


class MemberRoleUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=20)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return upper


class MemberResponse(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str | None = None
    name: str | None = None
    role: str
    joined_at: datetime
