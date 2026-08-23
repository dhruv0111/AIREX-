"""Provider and model schemas (spec §20–§27)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.integrations.provider import ProviderType


class ProviderCreate(BaseModel):
    provider_type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2000)
    base_url: str | None = Field(default=None, max_length=500)
    configuration: dict | None = Field(default=None)
    is_active: bool = True

    @field_validator("provider_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        try:
            ProviderType(v.upper())
        except ValueError:
            raise ValueError(f"Unsupported provider type: {v}")
        return v.upper()


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, max_length=500)
    configuration: dict | None = Field(default=None)
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE|ERROR)$")
    is_active: bool | None = None


class ProviderRotateRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=2000)


class ProviderResponse(BaseModel):
    id: UUID
    organization_id: UUID
    provider_type: str
    name: str
    masked_key: str | None = None
    base_url: str | None = None
    status: str
    last_connection_status: str | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ProviderTestResult(BaseModel):
    status: str
    provider: str
    model: str | None = None
    latency_ms: int | None = None
    error: str | None = None


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    model_identifier: str = Field(min_length=1, max_length=255)
    provider_id: UUID
    environment_id: UUID | None = None
    configuration: dict | None = Field(default=None)


class ModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    model_identifier: str | None = Field(default=None, min_length=1, max_length=255)
    environment_id: UUID | None = None
    configuration: dict | None = None
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE|ERROR)$")


class ModelResponse(BaseModel):
    id: UUID
    project_id: UUID
    provider_id: UUID
    environment_id: UUID | None = None
    name: str
    model_identifier: str
    configuration: dict | None = None
    status: str
    last_health_status: str | None = None
    last_checked_at: datetime | None = None
    last_latency_ms: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ModelInvokeRequest(BaseModel):
    messages: list[dict] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)


class ModelUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ModelInvokeResponse(BaseModel):
    id: str
    provider: str
    model: str
    content: str
    finish_reason: str
    usage: ModelUsage
    latency_ms: int
    metadata: dict = {}
    created_at: str


class ModelTestResult(BaseModel):
    status: str
    provider: str
    model: str
    latency_ms: int | None = None
    error: str | None = None


class ModelHealthResponse(BaseModel):
    status: str
    provider: str
    model: str | None = None
    last_checked_at: datetime
    latency_ms: int | None = None
    error: str | None = None
