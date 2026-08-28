"""Pydantic schemas for Alert Rule validation (Phase 8)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AlertRuleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    metric: str = Field(..., max_length=64)
    operator: str = Field(..., max_length=8)
    threshold: float
    duration_seconds: int = Field(600, ge=10)
    cooldown_seconds: int = Field(3600, ge=0)
    severity: str = Field("WARNING", max_length=20)
    environment: str | None = Field(None, max_length=64)
    is_enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    metric: str | None = Field(None, max_length=64)
    operator: str | None = Field(None, max_length=8)
    threshold: float | None = None
    duration_seconds: int | None = Field(None, ge=10)
    cooldown_seconds: int | None = Field(None, ge=0)
    severity: str | None = Field(None, max_length=20)
    environment: str | None = Field(None, max_length=64)
    is_enabled: bool | None = None
