"""Experiment schemas (Phase 6)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VariantCreate(BaseModel):
    model_id: UUID | None = None
    prompt_version_id: UUID | None = None
    prompt_content: str | None = None
    dataset_version_id: UUID | None = None
    configuration: dict | None = None


class VariantResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    variant_type: str
    model_id: UUID | None
    prompt_version_id: UUID | None
    dataset_version_id: UUID | None
    configuration: dict | None


class QualityGateCreate(BaseModel):
    metric_name: str = Field(min_length=1, max_length=100)
    gate_type: str = Field(default="CANDIDATE_VALUE", pattern="^(CANDIDATE_VALUE|RELATIVE_CHANGE|ABSOLUTE_CHANGE)$")
    operator: str = Field(pattern="^(GT|GTE|LT|LTE|EQ)$")
    threshold: float
    severity: str = Field(default="HIGH", pattern="^(NONE|LOW|MEDIUM|HIGH|CRITICAL)$")
    is_required: bool = True


class QualityGateResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    metric_name: str
    gate_type: str
    operator: str
    threshold: float
    severity: str
    is_required: bool


class ExperimentCreate(BaseModel):
    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    experiment_type: str = Field(default="MODEL_COMPARISON", pattern="^(MODEL_COMPARISON|PROMPT_COMPARISON|DATASET_COMPARISON|EVALUATOR_COMPARISON|CONFIGURATION_COMPARISON)$")
    dataset_version_id: UUID | None = None
    model_id: UUID | None = None
    configuration: dict | None = None
    baseline: VariantCreate
    candidate: VariantCreate
    quality_gates: list[QualityGateCreate] = Field(default_factory=list)


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ExperimentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    dataset_version_id: UUID | None
    model_id: UUID | None
    configuration: dict | None
    status: str
    experiment_type: str
    fingerprint: str | None
    duplicate_of: UUID | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    baseline: VariantResponse | None = None
    candidate: VariantResponse | None = None
    quality_gates: list[QualityGateResponse] = Field(default_factory=list)


class ExperimentRunResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    status: str
    baseline_run_id: UUID | None
    candidate_run_id: UUID | None
    created_by: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class ComparisonResponse(BaseModel):
    id: UUID
    run_id: UUID
    metric_name: str
    baseline_value: float | None
    candidate_value: float | None
    absolute_difference: float | None
    relative_difference: float | None
    classification: str
    statistical_metadata: dict | None


class RegressionResponse(BaseModel):
    id: UUID
    comparison_id: UUID
    metric_name: str
    severity: str
    baseline_value: float | None
    candidate_value: float | None
    threshold: float | None
    explanation: str | None


class QualityGateResultResponse(BaseModel):
    id: UUID
    run_id: UUID
    quality_gate_id: UUID
    metric_name: str
    actual_value: float | None
    status: str
