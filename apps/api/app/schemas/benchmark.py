"""Benchmark schemas (Phase 9)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BenchmarkSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    configuration: dict = Field(..., description="Configuration specifying dataset_version_id, baseline model, candidates, evaluators, and weights.")


class BenchmarkSuiteResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BenchmarkVersionCreate(BaseModel):
    configuration: dict


class BenchmarkVersionResponse(BaseModel):
    id: UUID
    benchmark_suite_id: UUID
    version: int
    configuration: dict
    configuration_hash: str
    dataset_version_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class BenchmarkRunCreate(BaseModel):
    benchmark_version_id: UUID | None = None


class BenchmarkRunResponse(BaseModel):
    id: UUID
    benchmark_suite_id: UUID
    benchmark_version_id: UUID
    status: str
    error_message: str | None
    reliability_score: float | None
    methodology_version: str
    configuration_hash: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class BenchmarkResultResponse(BaseModel):
    id: UUID
    benchmark_run_id: UUID
    evaluation_run_id: UUID
    baseline_run_id: UUID
    model_id: UUID
    reliability_score: float

    class Config:
        from_attributes = True


class ReliabilityEvidenceResponse(BaseModel):
    id: UUID
    benchmark_run_id: UUID
    benchmark_result_id: UUID | None
    metric_name: str
    baseline_value: float
    candidate_value: float
    absolute_change: float
    relative_change: float
    sample_size: int
    p_value: float | None
    effect_size: float | None
    confidence_interval_low: float | None
    confidence_interval_high: float | None
    significance: bool
    confidence: str

    class Config:
        from_attributes = True


class FailureClusterResponse(BaseModel):
    id: UUID
    benchmark_run_id: UUID
    benchmark_result_id: UUID | None
    failure_type: str
    error_message_pattern: str
    cluster_count: int
    cluster_percentage: float
    severity: str

    class Config:
        from_attributes = True


class RootCauseRecommendationResponse(BaseModel):
    id: UUID
    benchmark_run_id: UUID
    benchmark_result_id: UUID | None
    regression_attribution: str | None
    root_cause_analysis: str
    root_cause_confidence: str
    recommendation: str

    class Config:
        from_attributes = True


class BenchmarkRunDetailResponse(BaseModel):
    run: BenchmarkRunResponse
    results: list[BenchmarkResultResponse]
    evidences: list[ReliabilityEvidenceResponse]
    clusters: list[FailureClusterResponse]
    recommendation: RootCauseRecommendationResponse | None
