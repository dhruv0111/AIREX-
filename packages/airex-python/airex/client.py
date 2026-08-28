"""AIREX Python Observability SDK Client (Phase 8)."""

from __future__ import annotations

import contextvars
from datetime import datetime, UTC
import logging
import os
import queue
import random
import threading
import time
from typing import Any
import uuid
import httpx

logger = logging.getLogger("airex.sdk")

# ContextVar propagation for traces and nested parent-child span tracking
_current_trace_id = contextvars.ContextVar("_current_trace_id", default=None)
_current_span_id = contextvars.ContextVar("_current_span_id", default=None)


class AirexClient:
    """AIREX Client for production AI request tracing and quality observability."""

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        project_id: str | None = None,
        environment: str | None = None,
        service_name: str | None = None,
        disabled: bool | None = None,
    ) -> None:
        self.api_url = api_url or os.environ.get("AIREX_API_URL", "http://localhost:8000")
        self.api_token = api_token or os.environ.get("AIREX_API_TOKEN", "")
        self.project_id = project_id or os.environ.get("AIREX_PROJECT_ID", "")
        self.environment = environment or os.environ.get("AIREX_ENVIRONMENT", "production")
        self.service_name = service_name or os.environ.get("AIREX_SERVICE_NAME", "default-service")
        
        env_disabled = os.environ.get("AIREX_SDK_DISABLED", "false").lower() == "true"
        self.disabled = disabled if disabled is not None else env_disabled

        self._dropped_events = 0
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1000)
        self._client = httpx.Client(
            base_url=self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        if not self.disabled:
            self._start_worker()

    def _start_worker(self) -> None:
        with self._lock:
            if self._thread is None:
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._worker_loop, daemon=True)
                self._thread.start()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                batch = []
                # Attempt to pull elements up to 100
                while len(batch) < 100:
                    try:
                        # Non-blocking pull if we already have items in batch
                        timeout = 0.5 if not batch else 0.05
                        item = self._queue.get(timeout=timeout)
                        batch.append(item)
                        self._queue.task_done()
                    except queue.Empty:
                        break

                if batch:
                    self._send_batch(batch)
            except Exception as e:
                # Fail silently
                logger.debug(f"AIREX SDK background worker error: {e}")
                time.sleep(1)

    def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        if self.disabled or not self.project_id:
            return

        traces = [item["data"] for item in batch if item["type"] == "trace"]
        spans = [item["data"] for item in batch if item["type"] == "span"]

        payload = {
            "traces": traces,
            "spans": spans,
        }

        try:
            resp = self._client.post("/api/v1/observability/ingest", json=payload)
            if resp.status_code >= 400:
                logger.debug(f"AIREX Ingestion rejected batch: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.debug(f"AIREX Ingestion server connection failed: {e}")

    def enqueue_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self.disabled:
            return
        try:
            self._queue.put_nowait({"type": event_type, "data": data})
        except queue.Full:
            self._dropped_events += 1
            logger.debug("AIREX SDK local queue full, dropping observability event.")

    def flush(self, timeout: float = 2.0) -> None:
        """Manually flush all buffered events."""
        if self.disabled:
            return
        # Block until queue is empty
        start = time.time()
        while not self._queue.empty() and (time.time() - start) < timeout:
            time.sleep(0.05)

    def shutdown(self) -> None:
        """Stop background worker thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._client.close()

    def get_dropped_events(self) -> int:
        return self._dropped_events

    # Context Manager Helpers
    def trace(
        self,
        operation_name: str,
        trace_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> TraceContextManager:
        return TraceContextManager(
            client=self,
            operation_name=operation_name,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
        )

    def span(self, name: str, span_type: str = "CUSTOM") -> SpanContextManager:
        return SpanContextManager(client=self, name=name, span_type=span_type)

    def observe_llm(self, model: str, provider: str) -> LLMContextManager:
        return LLMContextManager(client=self, model=model, provider=provider)

    def record_quality(self, trace_id: str, quality_signals: dict[str, Any]) -> None:
        """Send custom quality signals for a trace."""
        if self.disabled:
            return
        try:
            payload = {
                "trace_id": trace_id,
                "signals": quality_signals,
            }
            self._client.post(f"/api/v1/projects/{self.project_id}/observability/quality-signals", json=payload)
        except Exception as e:
            logger.debug(f"AIREX SDK record_quality failed: {e}")


class TraceContextManager:
    def __init__(
        self,
        client: AirexClient,
        operation_name: str,
        trace_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.client = client
        self.operation_name = operation_name
        self.trace_id = trace_id or str(uuid.uuid4())
        self.user_id = user_id
        self.session_id = session_id
        self._start_time = None
        self._token_t = None

    def __enter__(self) -> TraceContextManager:
        self._start_time = datetime.now(UTC)
        self._token_t = _current_trace_id.set(self.trace_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        end_time = datetime.now(UTC)
        duration_ms = (end_time - self._start_time).total_seconds() * 1000.0

        status = "SUCCESS"
        error_msg = None
        if exc_type is not None:
            status = "ERROR"
            error_msg = str(exc_val)

        trace_data = {
            "trace_id": self.trace_id,
            "environment": self.client.environment,
            "service_name": self.client.service_name,
            "operation_name": self.operation_name,
            "start_time": self._start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "status": status,
            "error": error_msg,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }
        self.client.enqueue_event("trace", trace_data)
        if self._token_t:
            _current_trace_id.reset(self._token_t)


class SpanContextManager:
    def __init__(self, client: AirexClient, name: str, span_type: str = "CUSTOM") -> None:
        self.client = client
        self.name = name
        self.span_type = span_type
        self.span_id = str(uuid.uuid4())[:16]
        self._start_time = None
        self._token_s = None

    def __enter__(self) -> SpanContextManager:
        self._start_time = datetime.now(UTC)
        self._token_s = _current_span_id.set(self.span_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        end_time = datetime.now(UTC)
        duration_ms = (end_time - self._start_time).total_seconds() * 1000.0

        trace_id = _current_trace_id.get()
        # Fallback to random trace ID if span is executed outside trace context
        if not trace_id:
            trace_id = str(uuid.uuid4())

        status = "SUCCESS"
        error_msg = None
        if exc_type is not None:
            status = "ERROR"
            error_msg = str(exc_val)

        parent_span_id = None
        # We need to find the parent span context but make sure we don't return our own span ID
        # Since ContextVar is set upon entering __enter__, parent span is the one active before entering this context
        # In python, we can get parent by not checking the one currently active if reset, or managing nesting variables.
        # However, to be robust, we fetch current active before setting in __enter__
        # Let's save parent_span_id inside __enter__ instead!

        # (See __enter__ adjustments below)
        
        span_data = {
            "trace_id": trace_id,
            "span_id": self.span_id,
            "parent_span_id": getattr(self, "parent_span_id", None),
            "name": self.name,
            "span_type": self.span_type,
            "status": status,
            "error": error_msg,
            "start_time": self._start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": duration_ms,
        }
        self.client.enqueue_event("span", span_data)
        if self._token_s:
            _current_span_id.reset(self._token_s)

    # Overriding __enter__ to fetch active parent span id before setting ours
    def __enter__(self) -> SpanContextManager:
        self._start_time = datetime.now(UTC)
        self.trace_id = _current_trace_id.get()
        self.parent_span_id = _current_span_id.get()
        self._token_s = _current_span_id.set(self.span_id)
        return self


class LLMContextManager:
    def __init__(self, client: AirexClient, model: str, provider: str) -> None:
        self.client = client
        self.model = model
        self.provider = provider
        self.span_id = str(uuid.uuid4())[:16]
        self._start_time = None
        self._token_s = None
        self.input_tokens = None
        self.output_tokens = None
        self.total_tokens = None
        self.temperature = None
        self.max_tokens = None
        self.error_category = None
        self.attributes = {}

    def __enter__(self) -> LLMContextManager:
        self._start_time = datetime.now(UTC)
        self.trace_id = _current_trace_id.get()
        self.parent_span_id = _current_span_id.get()
        self._token_s = _current_span_id.set(self.span_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        end_time = datetime.now(UTC)
        duration_ms = (end_time - self._start_time).total_seconds() * 1000.0

        trace_id = _current_trace_id.get()
        if not trace_id:
            trace_id = str(uuid.uuid4())

        status = "SUCCESS"
        error_msg = None
        if exc_type is not None:
            status = "ERROR"
            error_msg = str(exc_val)
            self.error_category = "internal"

        # Auto-compute total tokens if input/output set
        if self.input_tokens is not None and self.output_tokens is not None:
            self.total_tokens = self.input_tokens + self.output_tokens

        span_data = {
            "trace_id": trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": f"LLM Invocation: {self.provider}/{self.model}",
            "span_type": "LLM",
            "status": status,
            "error": error_msg,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "error_category": self.error_category,
            "attributes": self.attributes,
            "start_time": self._start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_ms": duration_ms,
        }
        self.client.enqueue_event("span", span_data)
        if self._token_s:
            _current_span_id.reset(self._token_s)
