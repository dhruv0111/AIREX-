"""Pydantic schemas for Phase 10 Intelligence & Deployment Decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReleasePolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    environment_id: UUID | None = None
    min_reliability_score: float | None = Field(default=None, ge=0.0, le=100.0)
    max_regression_severity: str | None = Field(default=None, max_length=50)
    max_error_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    max_latency_ms: float | None = Field(default=None, ge=0.0)
    max_p95_latency_ms: float | None = Field(default=None, ge=0.0)
    max_cost: float | None = Field(default=None, ge=0.0)
    max_critical_alerts: int = Field(default=0, ge=0)
    min_statistical_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    min_sample_size: int | None = Field(default=None, ge=1)
    required_benchmark: bool = False
    required_evaluation: bool = False
    required_dataset_version_id: UUID | None = None
    required_quality_gates: bool = False
    max_evidence_age_days: int = Field(default=14, ge=1, le=365)
    custom_rules: dict[str, Any] | None = None


class ReleasePolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    environment_id: UUID | None = None
    min_reliability_score: float | None = Field(default=None, ge=0.0, le=100.0)
    max_regression_severity: str | None = Field(default=None, max_length=50)
    max_error_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    max_latency_ms: float | None = Field(default=None, ge=0.0)
    max_p95_latency_ms: float | None = Field(default=None, ge=0.0)
    max_cost: float | None = Field(default=None, ge=0.0)
    max_critical_alerts: int | None = Field(default=None, ge=0)
    min_statistical_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    min_sample_size: int | None = Field(default=None, ge=1)
    required_benchmark: bool | None = None
    required_evaluation: bool | None = None
    required_dataset_version_id: UUID | None = None
    required_quality_gates: bool | None = None
    max_evidence_age_days: int | None = Field(default=None, ge=1, le=365)
    custom_rules: dict[str, Any] | None = None


class ReleasePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    environment_id: UUID | None
    name: str
    description: str | None
    version: int
    min_reliability_score: float | None
    max_regression_severity: str | None
    max_error_rate: float | None
    max_latency_ms: float | None
    max_p95_latency_ms: float | None
    max_cost: float | None
    max_critical_alerts: int
    min_statistical_confidence: float | None
    min_sample_size: int | None
    required_benchmark: bool
    required_evaluation: bool
    required_dataset_version_id: UUID | None
    required_quality_gates: bool
    max_evidence_age_days: int
    custom_rules: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ReleaseDecisionCreate(BaseModel):
    environment_id: UUID
    model_id: UUID
    release_policy_id: UUID
    model_version: str | None = None
    model_configuration: dict[str, Any] | None = None


class ReleaseEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    release_decision_id: UUID
    source_type: str
    source_id: str
    environment_id: UUID | None
    methodology_version: str | None
    freshness_timestamp: datetime | None
    is_fresh: bool
    summary: dict[str, Any] | None
    created_at: datetime


class ReleaseCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    release_decision_id: UUID
    rule_name: str
    status: str
    actual_value: Any
    expected_value: Any
    evidence_reference: Any
    explanation: str
    is_blocking: bool
    created_at: datetime


class ReleaseDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    organization_id: UUID
    environment_id: UUID
    model_id: UUID
    provider_id: UUID
    release_policy_id: UUID
    policy_version: int
    model_version: str | None
    model_configuration: dict[str, Any] | None
    status: str
    outcome: str | None
    readiness_score: float | None
    readiness_breakdown: dict[str, Any] | None
    configuration_fingerprint: str
    stale_reason: str | None
    superseded_by_id: UUID | None
    evaluated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    checks: list[ReleaseCheckResponse] = Field(default_factory=list)
    evidences: list[ReleaseEvidenceResponse] = Field(default_factory=list)


class DecisionComparisonMetric(BaseModel):
    metric_name: str
    dimension: str
    previous_value: Any
    current_value: Any
    change_status: str  # IMPROVED, REGRESSED, UNCHANGED, NEW, REMOVED
    explanation: str


class DecisionComparisonResponse(BaseModel):
    current_decision_id: UUID
    previous_decision_id: UUID
    is_compatible: bool
    metrics: list[DecisionComparisonMetric]
    summary: str


class ProjectIntelligenceOverviewResponse(BaseModel):
    project_id: UUID
    overall_status: str  # READY, AT_RISK, BLOCKED, INSUFFICIENT_EVIDENCE
    readiness_score: float | None
    latest_decision: ReleaseDecisionResponse | None
    blocking_issues: list[str]
    warnings: list[str]
    model_comparisons: list[dict[str, Any]]
    recent_changes: list[dict[str, Any]]


class ProjectIntelligenceActionsResponse(BaseModel):
    project_id: UUID
    actions: list[dict[str, Any]]
