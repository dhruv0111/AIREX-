"""Organization schemas (spec §34)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "org"


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _default_slug(self):
        if not self.slug:
            self.slug = _slugify(self.name)
        return self


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime


class MemberResponse(BaseModel):
    user_id: UUID
    role: str
    email: str | None = None


class MembershipResponse(BaseModel):
    organization_id: UUID
    role: str
