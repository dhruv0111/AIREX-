"""Pydantic schemas for versioned model pricing configuration (Phase 8 §11)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PricingCreate(BaseModel):
    model_pattern: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=64)
    input_price_per_1k: float = Field(..., ge=0)
    output_price_per_1k: float = Field(..., ge=0)
    currency: str = Field("USD", min_length=3, max_length=8)
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class PricingUpdate(BaseModel):
    model_pattern: str | None = Field(None, min_length=1, max_length=255)
    provider: str | None = Field(None, min_length=1, max_length=64)
    input_price_per_1k: float | None = Field(None, ge=0)
    output_price_per_1k: float | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=8)
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def _validate_dates(self):
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_from >= self.effective_until
        ):
            raise ValueError("effective_from must be before effective_until.")
        return self


class PricingResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    model_pattern: str
    provider: str
    input_price_per_1k: float
    output_price_per_1k: float
    currency: str
    effective_from: datetime | None
    effective_until: datetime | None
    created_at: datetime
    updated_at: datetime
