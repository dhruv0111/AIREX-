"""CI and Service Token Pydantic schemas (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_SCOPES = {
    "experiments:read",
    "experiments:write",
    "experiments:run",
    "datasets:read",
    "models:read",
    "quality_gates:read",
}


class ServiceTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: int | None = Field(default=None, gt=0)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        for scope in v:
            if scope not in ALLOWED_SCOPES:
                raise ValueError(f"Invalid scope: {scope}. Allowed: {ALLOWED_SCOPES}")
        return v


class ServiceTokenResponse(BaseModel):
    id: UUID
    project_id: UUID
    organization_id: UUID
    name: str
    token_prefix: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class ServiceTokenCreatedResponse(ServiceTokenResponse):
    raw_token: str


class CIRunCreate(BaseModel):
    commit_sha: str = Field(min_length=1, max_length=255)
    branch: str = Field(min_length=1, max_length=255)
    repository: str = Field(min_length=1, max_length=255)
    pull_request_number: int | None = None
    pull_request_url: str | None = None
    ci_provider: str = Field(min_length=1, max_length=64)
    ci_run_id: str = Field(min_length=1, max_length=255)
    ci_job_id: str | None = None
    experiment_config: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class CIRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    experiment_id: UUID | None = None
    experiment_run_id: UUID | None = None
    commit_sha: str
    branch: str
    repository: str
    pull_request_number: int | None = None
    pull_request_url: str | None = None
    ci_provider: str
    ci_run_id: str
    ci_job_id: str | None = None
    status: str
    outcome: str | None = None
    duration_seconds: float | None = None
    completed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
