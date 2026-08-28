"""Observability service (Phase 8).

Provides production AI observability: batch ingestion (sampling + privacy +
cost), aggregated overview metrics, trace exploration, and model/provider /
cost / latency breakdowns for the dashboards.
"""

from __future__ import annotations

import math
import random
import hashlib
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories.observability import ObservabilityRepository
from app.repositories.project import ProjectRepository
from app.evaluations.cost import calculate_span_cost


def _percentile(values: list[float], percentile: float) -> float | None:
    """Linear-interpolated percentile. Returns None when there is no data."""
    if not values:
        return None
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return d0 + d1


class ObservabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._obs = ObservabilityRepository(session)
        self._projects = ProjectRepository(session)

    async def ingest_batch(
        self,
        *,
        project_id: UUID,
        org_id: UUID,
        traces: list[dict],
        spans: list[dict],
    ) -> dict[str, int]:
        """Ingest a batch of traces and spans applying sampling, privacy, and cost rules."""
        project = await self._projects.get_by_id(project_id)
        if not project:
            raise NotFoundError("Project not found.")

        # Resolve privacy mode and sample rate from project metadata/settings
        # Defaults to METADATA_ONLY privacy and 1.0 sample rate if not specified
        settings = project.settings or {}
        mode = settings.get("observability_mode", "METADATA_ONLY")
        sample_rate = float(settings.get("sample_rate", 1.0))
        error_bypass = settings.get("error_bypass_sampling", True)

        # 1. Process and filter Traces based on sampling
        traces_to_insert = []
        sampled_trace_ids = set()

        for t in traces:
            trace_id = t["trace_id"]

            # Parse dates if they are ISO strings
            if isinstance(t.get("start_time"), str):
                t["start_time"] = datetime.fromisoformat(t["start_time"])
            if isinstance(t.get("end_time"), str):
                t["end_time"] = datetime.fromisoformat(t["end_time"])

            # Determine if this trace has errors
            is_error = t.get("status") == "ERROR" or t.get("error") is not None

            # Sample logic: bypass if it's an error and bypass is enabled, else do normal sample check
            is_sampled = True
            if not (is_error and error_bypass):
                is_sampled = random.random() < sample_rate

            if is_sampled:
                # Apply privacy mapping to trace metadata
                t["metadata"] = self._apply_privacy_to_dict(t.get("metadata"), mode)
                traces_to_insert.append(t)
                sampled_trace_ids.add(trace_id)

        # 2. Process Spans belonging to sampled traces
        spans_to_insert = []
        for s in spans:
            trace_id = s["trace_id"]

            # Spans are only kept if their parent trace is sampled
            if trace_id not in sampled_trace_ids:
                continue

            # Parse dates if they are ISO strings
            if isinstance(s.get("start_time"), str):
                s["start_time"] = datetime.fromisoformat(s["start_time"])
            if isinstance(s.get("end_time"), str):
                s["end_time"] = datetime.fromisoformat(s["end_time"])

            # Apply privacy policy to span attributes
            s["attributes"] = self._apply_privacy_to_dict(s.get("attributes"), mode)

            # If it's an LLM span, calculate cost and normalize error category
            if s["span_type"] == "LLM":
                provider = s.get("provider")
                model = s.get("model")
                if provider and model:
                    cost = await calculate_span_cost(
                        self._session,
                        provider=provider,
                        model=model,
                        input_tokens=s.get("input_tokens"),
                        output_tokens=s.get("output_tokens"),
                    )
                    if cost is not None:
                        s["estimated_cost"] = float(cost)

                # Normalize error category if error is present
                if s.get("status") == "ERROR" and not s.get("error_category"):
                    s["error_category"] = "unknown"

            spans_to_insert.append(s)

        # 3. Perform batch inserts
        inserted_traces = await self._obs.insert_traces_batch(project_id, org_id, traces_to_insert)
        inserted_spans = await self._obs.insert_spans_batch(spans_to_insert)

        await self._session.commit()

        return {
            "traces_ingested": len(inserted_traces),
            "spans_ingested": len(inserted_spans),
        }

    def _apply_privacy_to_dict(self, data: dict | None, mode: str) -> dict | None:
        if not data:
            return data
        if mode == "FULL_CONTENT":
            return data

        # List of typical keys containing raw model prompts or responses
        content_keys = {
            "prompt", "response", "input", "output", "messages",
            "content", "completion", "text", "query",
        }

        result: dict = {}
        for k, v in data.items():
            if k.lower() in content_keys:
                if mode == "METADATA_ONLY":
                    # Exclude the prompt/response entirely
                    continue
                elif mode == "HASHED_CONTENT":
                    # Hash string representations
                    val_str = str(v)
                    result[f"{k}_hash"] = hashlib.sha256(val_str.encode()).hexdigest()
            else:
                result[k] = v
        return result

    async def _load_stats(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        """Load traces/spans in range and compute all aggregation stats."""
        traces = await self._obs.get_traces_in_range(
            project_id,
            start_time or (datetime.now(timezone.utc) - timedelta(days=3650)),
            end_time or datetime.now(timezone.utc),
        )
        if environment:
            traces = [t for t in traces if t.environment == environment]

        total_requests = len(traces)
        if total_requests == 0:
            # Return empty state indicator (nulls as per §69 requirement)
            return {
                "total_requests": 0,
                "success_rate": None,
                "error_rate": None,
                "errors": 0,
                "total_cost": None,
                "total_tokens": None,
                "input_tokens": None,
                "output_tokens": None,
                "latency_p50": None,
                "latency_p90": None,
                "latency_p95": None,
                "latency_p99": None,
                "latency_avg": None,
                "latency_max": None,
                "models": [],
                "providers": [],
                "environments": [],
                "spans": [],
            }

        # Compute error / success rates
        errors = sum(1 for t in traces if t.status == "ERROR")
        success_rate = (total_requests - errors) / total_requests
        error_rate = errors / total_requests

        # Load spans for these traces to calculate model/provider metrics
        trace_ids = [t.trace_id for t in traces]
        spans = await self._obs.get_spans_for_traces(trace_ids)

        total_cost = 0.0
        total_tokens = 0
        input_tokens = 0
        output_tokens = 0

        # Latency calculations based on non-null trace durations
        durations = [t.duration_ms for t in traces if t.duration_ms is not None]

        # Breakdown registries
        model_stats: dict[str, dict] = {}
        provider_stats: dict[str, dict] = {}
        env_stats: dict[str, dict] = {}

        for s in spans:
            if s.estimated_cost is not None:
                total_cost += float(s.estimated_cost)
            if s.total_tokens is not None:
                total_tokens += s.total_tokens
            if s.input_tokens is not None:
                input_tokens += s.input_tokens
            if s.output_tokens is not None:
                output_tokens += s.output_tokens

            env_name = None
            for tr in traces:
                if tr.trace_id == s.trace_id:
                    env_name = tr.environment
                    break
            if env_name:
                if env_name not in env_stats:
                    env_stats[env_name] = {"requests": 0, "errors": 0, "cost": 0.0, "tokens": 0}
                env_stats[env_name]["requests"] += 1
                if s.status == "ERROR":
                    env_stats[env_name]["errors"] += 1
                if s.estimated_cost is not None:
                    env_stats[env_name]["cost"] += float(s.estimated_cost)
                if s.total_tokens is not None:
                    env_stats[env_name]["tokens"] += s.total_tokens

            if s.span_type == "LLM" and s.model:
                m_key = s.model
                if m_key not in model_stats:
                    model_stats[m_key] = {"requests": 0, "errors": 0, "cost": 0.0, "tokens": 0, "durations": []}
                m_stat = model_stats[m_key]
                m_stat["requests"] += 1
                if s.status == "ERROR":
                    m_stat["errors"] += 1
                if s.estimated_cost is not None:
                    m_stat["cost"] += float(s.estimated_cost)
                if s.total_tokens is not None:
                    m_stat["tokens"] += s.total_tokens
                if s.duration_ms is not None:
                    m_stat["durations"].append(s.duration_ms)

            if s.span_type == "LLM" and s.provider:
                p_key = s.provider
                if p_key not in provider_stats:
                    provider_stats[p_key] = {"requests": 0, "errors": 0, "cost": 0.0, "tokens": 0, "durations": []}
                p_stat = provider_stats[p_key]
                p_stat["requests"] += 1
                if s.status == "ERROR":
                    p_stat["errors"] += 1
                if s.estimated_cost is not None:
                    p_stat["cost"] += float(s.estimated_cost)
                if s.total_tokens is not None:
                    p_stat["tokens"] += s.total_tokens
                if s.duration_ms is not None:
                    p_stat["durations"].append(s.duration_ms)

        # Build models breakdown list
        models_list = []
        for m_name, stat in model_stats.items():
            m_durations = stat["durations"]
            models_list.append({
                "model": m_name,
                "requests": stat["requests"],
                "success_rate": (stat["requests"] - stat["errors"]) / stat["requests"],
                "error_rate": stat["errors"] / stat["requests"],
                "tokens": stat["tokens"],
                "cost": stat["cost"],
                "latency_avg": sum(m_durations) / len(m_durations) if m_durations else None,
            })

        # Build providers breakdown list
        providers_list = []
        for p_name, stat in provider_stats.items():
            p_durations = stat["durations"]
            providers_list.append({
                "provider": p_name,
                "requests": stat["requests"],
                "success_rate": (stat["requests"] - stat["errors"]) / stat["requests"],
                "error_rate": stat["errors"] / stat["requests"],
                "tokens": stat["tokens"],
                "cost": stat["cost"],
                "latency_avg": sum(p_durations) / len(p_durations) if p_durations else None,
            })

        environments_list = [
            {
                "environment": env_name,
                "requests": stat["requests"],
                "success_rate": (stat["requests"] - stat["errors"]) / stat["requests"] if stat["requests"] else None,
                "error_rate": stat["errors"] / stat["requests"] if stat["requests"] else None,
                "tokens": stat["tokens"],
                "cost": stat["cost"],
            }
            for env_name, stat in env_stats.items()
        ]

        return {
            "total_requests": total_requests,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "errors": errors,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_p50": _percentile(durations, 0.50),
            "latency_p90": _percentile(durations, 0.90),
            "latency_p95": _percentile(durations, 0.95),
            "latency_p99": _percentile(durations, 0.99),
            "latency_avg": sum(durations) / len(durations) if durations else None,
            "latency_max": max(durations) if durations else None,
            "models": models_list,
            "providers": providers_list,
            "environments": environments_list,
            "spans": spans,
        }

    async def get_overview(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        stats = await self._load_stats(
            project_id, environment=environment, start_time=start_time, end_time=end_time
        )
        stats.pop("spans", None)
        return stats

    async def get_models(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        stats = await self._load_stats(
            project_id, environment=environment, start_time=start_time, end_time=end_time
        )
        return {
            "total_requests": stats["total_requests"],
            "models": stats["models"],
        }

    async def get_providers(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        stats = await self._load_stats(
            project_id, environment=environment, start_time=start_time, end_time=end_time
        )
        return {
            "total_requests": stats["total_requests"],
            "providers": stats["providers"],
        }

    async def get_cost(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        stats = await self._load_stats(
            project_id, environment=environment, start_time=start_time, end_time=end_time
        )
        total_cost = stats["total_cost"]
        total_requests = stats["total_requests"]
        return {
            "total_cost": total_cost,
            "cost_per_request": (total_cost / total_requests) if total_cost is not None and total_requests else None,
            "cost_by_model": [
                {"model": m["model"], "cost": m["cost"]} for m in stats["models"]
            ],
            "cost_by_provider": [
                {"provider": p["provider"], "cost": p["cost"]} for p in stats["providers"]
            ],
            "cost_by_environment": [
                {"environment": e["environment"], "cost": e["cost"]} for e in stats["environments"]
            ],
        }

    async def get_latency(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        stats = await self._load_stats(
            project_id, environment=environment, start_time=start_time, end_time=end_time
        )
        return {
            "total_requests": stats["total_requests"],
            "latency_p50": stats["latency_p50"],
            "latency_p90": stats["latency_p90"],
            "latency_p95": stats["latency_p95"],
            "latency_p99": stats["latency_p99"],
            "latency_avg": stats["latency_avg"],
            "latency_max": stats["latency_max"],
        }

    async def get_traces_paginated(
        self,
        project_id: UUID,
        *,
        environment: str | None = None,
        status: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        trace_id: str | None = None,
        error_category: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        traces, total = await self._obs.get_traces_paginated(
            project_id,
            environment=environment,
            status=status,
            model=model,
            provider=provider,
            trace_id=trace_id,
            error_category=error_category,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        return {
            "traces": traces,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_trace_detail(self, project_id: UUID, trace_id: str) -> dict:
        trace = await self._obs.get_trace_by_client_id(project_id, trace_id)
        if not trace:
            raise NotFoundError("Trace not found.")

        spans = await self._obs.get_spans_by_trace(trace_id)
        return {
            "trace": trace,
            "spans": spans,
        }

    async def record_quality_signals(self, project_id: UUID, trace_id: str, signals: dict) -> None:
        """Update trace quality score and store quality signals in metadata."""
        trace = await self._obs.get_trace_by_client_id(project_id, trace_id)
        if not trace:
            raise NotFoundError("Trace not found.")

        # Update metadata quality logs
        meta = dict(trace.metadata_ or {})
        quality_signals = meta.get("quality_signals", {})
        quality_signals.update(signals)
        meta["quality_signals"] = quality_signals
        trace.metadata_ = meta

        # Auto-compute quality score if a feedback or score rating is available
        # e.g., thumbs_up = 1.0, thumbs_down = 0.0, human_rating / rating scale
        scores = []
        if "thumbs_up" in quality_signals:
            scores.append(1.0 if quality_signals["thumbs_up"] else 0.0)
        if "thumbs_down" in quality_signals:
            scores.append(0.0 if quality_signals["thumbs_down"] else 1.0)
        if "human_rating" in quality_signals:
            scores.append(float(quality_signals["human_rating"]))
        if "rating" in quality_signals:
            scores.append(float(quality_signals["rating"]))
        if "task_success" in quality_signals:
            scores.append(1.0 if quality_signals["task_success"] else 0.0)

        if scores:
            trace.quality_score = sum(scores) / len(scores)

        # Log audit event
        from app.repositories.audit import AuditRepository
        audit = AuditRepository(self._session)
        await audit.record(
            action="QUALITY_SIGNAL_RECORDED",
            organization_id=trace.organization_id,
            user_id=None,
            resource_type="trace",
            resource_id=trace.id,
            metadata={"trace_id": trace_id, "signals": signals},
        )

        await self._session.commit()
