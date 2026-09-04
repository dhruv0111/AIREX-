"""Pydantic schemas for Phase 11 AI Agent Evaluation, Trajectory Testing & Agent Reliability."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------- Tool Schemas
class ToolDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    safety_level: str = Field(default="LOW", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    metadata: dict[str, Any] | None = None


class ToolDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    version: int
    safety_level: str
    timeout_seconds: int
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------- Agent Schemas
class AgentDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    agent_type: str = Field(default="TOOL_AGENT", pattern="^(CHAT_AGENT|TOOL_AGENT|RAG_AGENT|WORKFLOW_AGENT|MULTI_AGENT)$")
    provider_id: UUID | None = None
    model_id: UUID | None = None
    environment_id: UUID | None = None
    system_prompt: str | None = None
    tool_manifest: list[dict[str, Any] | str] | None = None
    retrieval_configuration: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class AgentDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    agent_type: str | None = Field(default=None, pattern="^(CHAT_AGENT|TOOL_AGENT|RAG_AGENT|WORKFLOW_AGENT|MULTI_AGENT)$")
    provider_id: UUID | None = None
    model_id: UUID | None = None
    environment_id: UUID | None = None
    system_prompt: str | None = None
    tool_manifest: list[dict[str, Any] | str] | None = None
    retrieval_configuration: dict[str, Any] | None = None
    configuration: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    is_active: bool | None = None


class AgentDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    agent_type: str
    version: int
    provider_id: UUID | None
    model_id: UUID | None
    environment_id: UUID | None
    system_prompt: str | None
    tool_manifest: list[Any] | None
    retrieval_configuration: dict[str, Any] | None
    configuration: dict[str, Any] | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    configuration_fingerprint: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------- Agent Task Schema
class AgentTaskSchema(BaseModel):
    """Standardized schema for Agent Task Datasets (Core Feature 3)."""
    task_id: str
    instruction: str = Field(min_length=1)
    initial_context: dict[str, Any] = Field(default_factory=dict)
    expected_goal: dict[str, Any] = Field(default_factory=dict)
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    max_steps: int = Field(default=10, ge=1, le=100)
    max_tool_calls: int = Field(default=20, ge=0, le=200)
    success_criteria: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------- Agent Run Schemas
class AgentRunCreate(BaseModel):
    environment_id: UUID | None = None
    dataset_version_id: UUID | None = None
    test_case_id: UUID | None = None
    task: AgentTaskSchema | None = None
    metadata: dict[str, Any] | None = None


class AgentTrajectoryStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_run_id: UUID
    step_number: int
    step_type: str
    status: str
    parent_step_id: UUID | None
    span_id: str | None
    tool_definition_id: UUID | None
    tool_name: str | None
    tool_call_id: str | None
    tool_arguments: dict[str, Any] | None
    tool_result: dict[str, Any] | None
    model_input: str | None
    model_output: str | None
    error_category: str | None
    error_message: str | None
    duration_ms: float | None
    timestamp: datetime
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    agent_id: UUID
    agent_version: int
    agent_fingerprint: str
    dataset_version_id: UUID | None
    test_case_id: UUID | None
    environment_id: UUID | None
    trace_id: str | None
    status: str
    goal_completion_status: str
    total_steps: int
    total_tool_calls: int
    successful_tool_calls: int
    failed_tool_calls: int
    recovered_failures: int
    unrecovered_failures: int
    loops_detected: int
    safety_violations: int
    duration_ms: float | None
    estimated_cost: float | None
    total_tokens: int | None
    final_output: str | None
    error_message: str | None
    reliability_score: float | None
    reliability_breakdown: dict[str, Any] | None
    evaluation_checks: list[dict[str, Any]] | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    trajectory_steps: list[AgentTrajectoryStepResponse] = Field(default_factory=list)


# ------------------------------------------------------------- Trajectory Evaluation
class TrajectoryCheckResult(BaseModel):
    check_name: str
    status: str  # PASS, FAIL, WARNING, NOT_APPLICABLE
    actual_value: Any
    expected_value: Any
    is_blocking: bool
    explanation: str
    step_references: list[int] = Field(default_factory=list)


class TrajectoryEvaluationResponse(BaseModel):
    run_id: UUID
    overall_status: str  # PASS, BLOCKED, FAIL, WARNING
    checks: list[TrajectoryCheckResult]
    reliability_score: float | None
    loops_detected: int
    safety_violations: int
    recovery_rate: float
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class AgentReliabilityResponse(BaseModel):
    agent_id: UUID
    agent_version: int
    total_runs: int
    reliability_score: float | None
    goal_completion_rate: float
    tool_correctness_rate: float
    recovery_rate: float
    safety_status: str  # PASS, BLOCKED
    dimension_scores: dict[str, Any]
    status: str  # READY, AT_RISK, BLOCKED, INSUFFICIENT_EVIDENCE
