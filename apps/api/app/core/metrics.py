"""Prometheus metrics (spec §59–§60, AT-029 area).

Exposed metrics:
  http_requests_total
  http_request_duration_seconds
  http_errors_total
  database_connection_status
  queue_jobs_total
  queue_jobs_failed_total
"""

from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration (seconds)",
    ["method", "path"],
)
http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP 5xx errors",
    ["method", "path"],
)
database_connection_status = Gauge(
    "database_connection_status",
    "1 if the database is reachable, else 0",
)
queue_jobs_total = Counter(
    "queue_jobs_total",
    "Total jobs enqueued",
)
queue_jobs_failed_total = Counter(
    "queue_jobs_failed_total",
    "Total jobs failed",
)
# ---- Phase 7 CI/CD Metrics ----
ci_runs_total = Counter(
    "airex_ci_runs_total",
    "Total CI runs triggered",
    ["provider", "status"],
)
ci_run_failures_total = Counter(
    "airex_ci_run_failures_total",
    "Total CI run failures by category",
    ["category"],
)
ci_run_duration_seconds = Histogram(
    "airex_ci_run_duration_seconds",
    "CI run execution duration in seconds",
)
quality_gate_enforcements_total = Counter(
    "airex_quality_gate_enforcements_total",
    "Total quality gate policy enforcements",
    ["metric_name"],
)
quality_gate_blocks_total = Counter(
    "airex_quality_gate_blocks_total",
    "Total quality gate policy blocks",
    ["metric_name"],
)
service_token_auth_failures_total = Counter(
    "airex_service_token_auth_failures_total",
    "Total service token authentication failures",
)

# ---- Phase 1 model observability (spec §30) ----
model_requests_total = Counter(
    "airex_model_requests_total",
    "Total model invocations",
    ["provider", "status"],
)
model_request_errors_total = Counter(
    "airex_model_request_errors_total",
    "Model invocation errors",
    ["provider", "error_category"],
)
model_request_duration_seconds = Histogram(
    "airex_model_request_duration_seconds",
    "Model invocation duration (seconds)",
    ["provider"],
)
model_input_tokens_total = Counter(
    "airex_model_input_tokens_total",
    "Total input tokens consumed",
    ["provider"],
)
model_output_tokens_total = Counter(
    "airex_model_output_tokens_total",
    "Total output tokens produced",
    ["provider"],
)

# ---- Phase 3 evaluation observability (spec §47) ----
# No high-cardinality labels (no evaluation_id/test_case_id/request_id).
evaluation_runs_total = Counter(
    "airex_evaluations_total",
    "Total evaluation runs",
    ["status"],
)
evaluation_duration_seconds = Histogram(
    "airex_evaluation_duration_seconds",
    "Evaluation run duration (seconds)",
)
evaluation_tests_total = Counter(
    "airex_evaluation_tests_total",
    "Total test cases evaluated",
)
evaluation_tests_passed_total = Counter(
    "airex_evaluation_tests_passed_total",
    "Total test cases passed",
)
evaluation_tests_failed_total = Counter(
    "airex_evaluation_tests_failed_total",
    "Total test cases failed",
)
evaluation_errors_total = Counter(
    "airex_evaluation_errors_total",
    "Total test case errors",
)

# ---- Phase 4 LLM-judge observability (spec §49) ----
# No high-cardinality labels: never prompt/response/evaluation_id/test_case_id.
llm_judge_requests_total = Counter(
    "airex_llm_judge_requests_total",
    "Total LLM judge model requests",
)
llm_judge_errors_total = Counter(
    "airex_llm_judge_errors_total",
    "Total LLM judge errors",
)
llm_judge_duration_seconds = Histogram(
    "airex_llm_judge_duration_seconds",
    "LLM judge request duration (seconds)",
)
llm_judge_tokens_total = Counter(
    "airex_llm_judge_tokens_total",
    "Total tokens consumed by LLM judge calls",
)
llm_judge_cache_hits_total = Counter(
    "airex_llm_judge_cache_hits_total",
    "Total LLM judge cache hits",
)

# ---- Phase 5 test-generation observability (spec §"GENERATION METRICS") ----
# No high-cardinality labels: never prompt/output/request_id/generation_request_id.
generation_requests_total = Counter(
    "airex_generation_requests_total",
    "Total test-generation requests",
    ["status"],
)
generation_duration_seconds = Histogram(
    "airex_generation_duration_seconds",
    "Test-generation request duration (seconds)",
)
generation_candidates_total = Counter(
    "airex_generation_candidates_total",
    "Total generated candidates",
    ["status"],
)
generation_candidates_duplicates_total = Counter(
    "airex_generation_candidates_duplicates_total",
    "Total duplicate generated candidates",
)
generation_candidates_rejected_total = Counter(
    "airex_generation_candidates_rejected_total",
    "Total generated candidates rejected by schema validation",
)
generation_errors_total = Counter(
    "airex_generation_errors_total",
    "Total generation errors",
    ["category"],
)
generation_provider_requests_total = Counter(
    "airex_generation_provider_requests_total",
    "Total generator model provider requests",
)


# ---- Phase 6 experiment & benchmarking observability ----
airex_experiments_total = Counter(
    "airex_experiments_total",
    "Total experiments completed",
)
airex_experiment_runs_total = Counter(
    "airex_experiment_runs_total",
    "Total experiment runs",
    ["status"],
)
airex_experiment_failures_total = Counter(
    "airex_experiment_failures_total",
    "Total experiment failures",
)
airex_experiment_duration_seconds = Histogram(
    "airex_experiment_duration_seconds",
    "Experiment run duration (seconds)",
)
airex_experiment_regressions_total = Counter(
    "airex_experiment_regressions_total",
    "Total regressions detected",
)
airex_quality_gate_failures_total = Counter(
    "airex_quality_gate_failures_total",
    "Total quality gate failures",
)

# ---- Phase 8 Observability Metrics ----
airex_observability_ingested_total = Counter(
    "airex_observability_ingested_total",
    "Total observability events (traces + spans) ingested",
)
airex_observability_ingestion_errors_total = Counter(
    "airex_observability_ingestion_errors_total",
    "Total observability ingestion failures",
)
airex_trace_duration_seconds = Histogram(
    "airex_trace_duration_seconds",
    "Duration of end-to-end traces in seconds",
)
airex_llm_requests_total = Counter(
    "airex_llm_requests_total",
    "Total LLM requests captured in observability",
    ["provider", "model"],
)
airex_llm_errors_total = Counter(
    "airex_llm_errors_total",
    "Total LLM request errors captured in observability",
    ["provider", "model", "error_category"],
)
airex_llm_tokens_total = Counter(
    "airex_llm_tokens_total",
    "Total tokens consumed by LLM requests",
    ["provider", "model"],
)
airex_llm_cost_total = Counter(
    "airex_llm_cost_total",
    "Estimated total cost of LLM invocations",
    ["provider", "model"],
)
airex_alerts_triggered_total = Counter(
    "airex_alerts_triggered_total",
    "Total alerts triggered",
    ["metric", "severity"],
)
airex_alerts_resolved_total = Counter(
    "airex_alerts_resolved_total",
    "Total alerts resolved",
    ["metric"],
)
airex_notifications_sent_total = Counter(
    "airex_notifications_sent_total",
    "Total alert notifications sent successfully",
    ["channel"],
)
airex_notifications_failed_total = Counter(
    "airex_notifications_failed_total",
    "Total alert notifications that failed to send",
    ["channel"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request metrics and emit them to Prometheus."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        # Normalize route params into a stable label.
        for route in request.app.routes:
            if getattr(route, "path", None) and route.path != "/{path:path}":
                if route.path == path:
                    break
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            http_errors_total.labels(method=request.method, path=path).inc()
            raise
        finally:
            duration = time.perf_counter() - start
            http_request_duration_seconds.labels(method=request.method, path=path).observe(duration)
            try:
                status = getattr(response, "status_code", 500) if "response" in locals() else 500
            except Exception:
                status = 500
            http_requests_total.labels(method=request.method, path=path, status=str(status)).inc()
        return response


def metrics_response() -> Response:
    """Return Prometheus-formatted metrics (GET /metrics)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def report_db_status(ok: bool) -> None:
    database_connection_status.set(1 if ok else 0)


def metrics_enabled() -> bool:
    from app.core.config import get_settings

    return get_settings().prometheus_enabled
