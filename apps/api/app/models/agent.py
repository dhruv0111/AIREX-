"""Domain models for Phase 11 AI Agent Evaluation, Trajectory Testing & Agent Reliability."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ToolDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tool definition containing metadata and input/output JSON schemas."""

    __tablename__ = "tool_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_tool_project_name_version"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    safety_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class AgentDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Agent definition representing an evaluable AI agent configuration."""

    __tablename__ = "agent_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_agent_project_name_version"),
        Index("ix_agent_definitions_fingerprint", "configuration_fingerprint"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(50), default="TOOL_AGENT", nullable=False)  # CHAT_AGENT, TOOL_AGENT, RAG_AGENT, WORKFLOW_AGENT, MULTI_AGENT
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL"), nullable=True
    )
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_manifest: Mapped[list | None] = mapped_column(JSON, nullable=True)
    retrieval_configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    configuration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    runs: Mapped[list[AgentRun]] = relationship(
        "AgentRun", back_populates="agent", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentRun(UUIDPrimaryKeyMixin, Base):
    """An execution run of an agent on a task or task dataset."""

    __tablename__ = "agent_runs"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_definitions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_version: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="SET NULL"), nullable=True
    )
    test_case_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True
    )
    environment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    trace_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    # Lifecycle: PENDING, QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, TIMED_OUT
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True, nullable=False)
    # Goal: COMPLETED, PARTIAL, FAILED, UNKNOWN
    goal_completion_status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)

    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovered_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unrecovered_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    loops_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safety_violations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reliability_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluation_checks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[AgentDefinition] = relationship("AgentDefinition", back_populates="runs")
    trajectory_steps: Mapped[list[AgentTrajectoryStep]] = relationship(
        "AgentTrajectoryStep", back_populates="agent_run", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentTrajectoryStep(UUIDPrimaryKeyMixin, Base):
    """Step in an agent trajectory execution."""

    __tablename__ = "agent_trajectory_steps"
    __table_args__ = (
        Index("ix_agent_trajectory_steps_step_no", "agent_run_id", "step_number"),
    )

    agent_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Type: MODEL_REQUEST, MODEL_RESPONSE, TOOL_CALL, TOOL_RESULT, RETRIEVAL, OBSERVATION, DECISION, ERROR, RETRY, FINAL
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, FAIL, WARNING, SKIPPED
    parent_step_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_trajectory_steps.id", ondelete="SET NULL"), nullable=True
    )
    span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_definition_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tool_definitions.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_arguments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    agent_run: Mapped[AgentRun] = relationship("AgentRun", back_populates="trajectory_steps")
