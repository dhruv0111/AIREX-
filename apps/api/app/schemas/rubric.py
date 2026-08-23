"""Rubric schemas (Phase 4 §22–§23)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RubricCriterion(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    weight: float = Field(ge=0)
    min_score: float = 0.0
    max_score: float = 1.0


class RubricCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    criteria: list[RubricCriterion] = Field(min_length=1)


class RubricUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    criteria: list[RubricCriterion] | None = None


class RubricResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    version: int
    criteria: list[dict]
    status: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None
