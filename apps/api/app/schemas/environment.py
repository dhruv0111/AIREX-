"""Environment schemas (spec §32–§35)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ENVIRONMENT_TYPES = ("DEVELOPMENT", "STAGING", "PRODUCTION")


class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    environment_type: str = Field(min_length=1, max_length=20)
    default_model_id: UUID | None = None
    evaluation_policy: dict | None = None
    observability_policy: dict | None = None
    data_retention_policy: dict | None = None

    @field_validator("environment_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ENVIRONMENT_TYPES:
            raise ValueError(f"environment_type must be one of {ENVIRONMENT_TYPES}")
        return upper


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")
    default_model_id: UUID | None = None
    evaluation_policy: dict | None = None
    observability_policy: dict | None = None
    data_retention_policy: dict | None = None


class EnvironmentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    environment_type: str
    status: str
    default_model_id: UUID | None = None
    evaluation_policy: dict | None = None
    observability_policy: dict | None = None
    data_retention_policy: dict | None = None
    created_at: datetime
    updated_at: datetime
