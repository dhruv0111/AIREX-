"""Generation request + generated candidate schemas (Phase 5)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationConfigurationSchema(BaseModel):
    """Normalized generation configuration (validated by the domain package)."""

    generation_types: list[str] = Field(default_factory=lambda: ["BASIC"])
    difficulty_distribution: dict[str, float] | None = None


class GenerationCreate(BaseModel):
    project_id: UUID
    environment_id: UUID | None = None
    source_type: str = Field(default="MANUAL_INSTRUCTION", min_length=1, max_length=32)
    source_reference: dict | None = None
    generation_type: str = Field(default="BASIC", min_length=1, max_length=32)
    instruction: str | None = Field(default=None, max_length=4000)
    count: int = Field(default=20, ge=1, le=100)
    configuration: GenerationConfigurationSchema = Field(
        default_factory=GenerationConfigurationSchema
    )
    generator_model_id: UUID


class GenerationResponse(BaseModel):
    id: UUID
    project_id: UUID
    environment_id: UUID | None
    source_type: str
    source_reference: dict | None
    generation_type: str
    instruction: str | None
    count: int
    configuration: dict | None
    status: str
    generator_model_snapshot: dict | None
    prompt_version: str | None
    source_snapshot: dict | None
    candidate_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    created_by: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class GeneratedCandidateResponse(BaseModel):
    id: UUID
    generation_request_id: UUID
    project_id: UUID
    input: str
    expected_output: str | None
    context: dict | None
    category: str | None
    generation_type: str
    difficulty: str | None
    status: str
    quality_score: float | None
    fingerprint: str
    duplicate_of: UUID | None
    dataset_version_id: UUID | None
    metadata: dict | None
    created_at: datetime


class CandidateReview(BaseModel):
    action: str = Field(pattern="^(approve|reject|APPROVE|REJECT)$")


class CreateDatasetVersionFromCandidates(BaseModel):
    dataset_id: UUID
    candidate_ids: list[UUID] = Field(min_length=1)


class DatasetVersionFromCandidatesResponse(BaseModel):
    dataset_version_id: UUID
    dataset_id: UUID
    version_number: int
    record_count: int
    checksum: str
