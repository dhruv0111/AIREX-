"""Evaluation schemas (Phase 3 §24, §26–§28, §40; Phase 4 §18, §38, §41, §43)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluatorConfig(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    enabled: bool = True
    # Extra evaluator parameters (e.g. tolerance, min_length/max_length).
    params: dict = Field(default_factory=dict)
    # Phase 4 — LLM judge + combined-scoring fields (spec §18, §41, §43).
    judge_model_id: UUID | None = None
    rubric_id: UUID | None = None
    threshold: float | None = Field(default=None, ge=0, le=1)
    reference_required: bool | None = None
    weight: float | None = Field(default=None, ge=0)


class EvaluationExecutionConfig(BaseModel):
    max_concurrency: int = Field(default=5, ge=1, le=50)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    stop_on_error: bool = False
    # Phase 4 — combined pass policy (spec §41).
    pass_policy: str = Field(default="ALL", pattern="^(ANY|ALL|WEIGHTED)$")
    threshold: float | None = Field(default=None, ge=0, le=1)


class EvaluationConfiguration(BaseModel):
    evaluators: list[EvaluatorConfig] = Field(default_factory=list, min_length=1)
    execution: EvaluationExecutionConfig = Field(default_factory=EvaluationExecutionConfig)


class EvaluationCreate(BaseModel):
    project_id: UUID
    environment_id: UUID | None = None
    dataset_version_id: UUID
    model_id: UUID
    configuration: EvaluationConfiguration


class EvaluationResponse(BaseModel):
    id: UUID
    project_id: UUID
    environment_id: UUID | None
    dataset_version_id: UUID | None
    model_id: UUID | None
    status: str
    configuration: dict | None
    model_snapshot: dict | None
    dataset_checksum: str | None
    evaluator_versions: dict | None
    judge_model_id: UUID | None
    judge_rubric_id: UUID | None
    judge_model_snapshot: dict | None
    judge_rubric_snapshot: dict | None
    judge_prompt_version: str | None
    total_tests: int
    completed_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    metrics: dict | None
    created_by: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class EvaluationResultResponse(BaseModel):
    id: UUID
    evaluation_run_id: UUID
    test_case_id: UUID | None
    actual_output: str | None
    # List of per-evaluator scores: [{evaluator, version, score, passed, reason, metadata}].
    score: list[dict] | None
    status: str
    failure_type: str | None
    failure_message: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: float | None
    explanation: str | None
    judge_score: float | None
    judge_confidence: float | None
    judge_reasoning: str | None
    judge_criteria_scores: dict | None
    judge_model_snapshot: dict | None
    judge_rubric_snapshot: dict | None
    judge_prompt_version: str | None
    combined_score: float | None
    created_at: datetime
