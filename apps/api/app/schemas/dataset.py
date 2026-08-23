"""Dataset, version and test-case schemas (Phase 2 §13–§18, §23–§31)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    metadata: dict | None = None


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    metadata: dict | None = None
    status: str | None = Field(default=None, pattern="^(ACTIVE|ARCHIVED)$")


class DatasetResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: str
    metadata: dict | None
    version_count: int
    latest_version: int | None
    record_count: int
    created_at: datetime
    updated_at: datetime


class DatasetVersionCreate(BaseModel):
    # The source format (csv/json/jsonl). The file itself is uploaded separately.
    format: str = Field(default="jsonl", min_length=1, max_length=10)


class DatasetVersionResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    version_number: int
    record_count: int
    checksum: str
    format: str
    status: str
    created_by: UUID | None
    created_at: datetime


class TestCaseResponse(BaseModel):
    id: UUID
    dataset_version_id: UUID
    row_number: int | None
    input: str
    expected_output: str | None
    context: dict | None
    category: str | None
    difficulty: str | None
    metadata: dict | None
    status: str
    created_at: datetime


class ValidationIssueSchema(BaseModel):
    row: int | None = None
    field: str | None = None
    code: str
    message: str


class ValidationResultSchema(BaseModel):
    valid: bool
    record_count: int
    errors: list[ValidationIssueSchema] = Field(default_factory=list)
    warnings: list[ValidationIssueSchema] = Field(default_factory=list)
