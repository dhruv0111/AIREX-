"""Project schemas (spec §35)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "project"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    application_type: str = Field(default="generic_llm", max_length=64)

    @model_validator(mode="after")
    def _default_slug(self):
        if not self.slug:
            self.slug = _slugify(self.name)
        return self


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    application_type: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, pattern="^(ACTIVE|ARCHIVED)$")


class ProjectResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None
    application_type: str
    status: str
    created_at: datetime
    updated_at: datetime
