"""Pydantic validation schemas for Phase 8 AI Observability Ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class SpanIngestSchema(BaseModel):
    trace_id: str = Field(..., max_length=128)
    span_id: str = Field(..., max_length=64)
    parent_span_id: str | None = Field(None, max_length=64)
    name: str = Field(..., max_length=255)
    span_type: str = Field(..., max_length=64) # LLM, RETRIEVAL, TOOL, PROMPT, EVALUATION, CUSTOM
    start_time: datetime
    end_time: datetime | None = None
    status: str = Field("SUCCESS", max_length=32)
    error: str | None = Field(None, max_length=1000)
    attributes: dict[str, Any] | None = None

    # LLM Invocation specific
    provider: str | None = Field(None, max_length=64)
    model: str | None = Field(None, max_length=255)
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    error_category: str | None = Field(None, max_length=64)
    duration_ms: float | None = None


class TraceIngestSchema(BaseModel):
    trace_id: str = Field(..., max_length=128)
    environment: str = Field("production", max_length=64)
    service_name: str | None = Field(None, max_length=255)
    operation_name: str | None = Field(None, max_length=255)
    start_time: datetime
    end_time: datetime | None = None
    status: str | None = Field(None, max_length=32)
    error: str | None = Field(None, max_length=1000)
    user_id: str | None = Field(None, max_length=255)
    session_id: str | None = Field(None, max_length=255)
    deployment_version: str | None = Field(None, max_length=255)
    git_commit: str | None = Field(None, max_length=255)
    quality_score: float | None = None
    metadata: dict[str, Any] | None = None


class IngestBatchPayload(BaseModel):
    traces: list[TraceIngestSchema] = []
    spans: list[SpanIngestSchema] = []
