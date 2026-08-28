"""Alert and Anomaly Detection Engine (Phase 8)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, UTC
import logging
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertRule, Alert
from app.models.trace import Trace, Span
from app.models.project import Project
from app.services.notifications import WebhookNotificationProvider

logger = logging.getLogger("airex.alerts")


async def evaluate_alert_rules(session: AsyncSession) -> dict:
    """Scan all active alert rules, compute sliding window metrics, and manage incidents."""
    # 1. Fetch enabled rules
    res = await session.execute(select(AlertRule).where(AlertRule.is_enabled == True))
    rules = res.scalars().all()

    evaluated_count = 0
    triggered_count = 0
    resolved_count = 0

    for rule in rules:
        evaluated_count += 1
        window_start = datetime.now(UTC) - timedelta(seconds=rule.duration_seconds)
        
        # Load project for settings (webhook configurations)
        project = await session.get(Project, rule.project_id)
        settings = (project.settings or {}) if project else {}
        webhook_url = settings.get("webhook_url")
        webhook_secret = settings.get("webhook_secret")

        # 2. Fetch traces in window
        stmt_traces = select(Trace).where(
            and_(
                Trace.project_id == rule.project_id,
                Trace.start_time >= window_start
            )
        )
        if rule.environment:
            stmt_traces = stmt_traces.where(Trace.environment == rule.environment)
            
        res_traces = await session.execute(stmt_traces)
        traces = list(res_traces.scalars().all())
        total_traces = len(traces)

        # 3. Compute observed value for metric
        observed = None
        if rule.metric == "request_rate":
            # request per minute
            observed = total_traces / (rule.duration_seconds / 60.0)
        
        elif rule.metric == "error_rate":
            errors = sum(1 for t in traces if t.status == "ERROR")
            observed = (errors / total_traces) if total_traces > 0 else 0.0

        elif rule.metric == "latency_p95":
            durations = [t.duration_ms for t in traces if t.duration_ms is not None]
            if durations:
                sorted_vals = sorted(durations)
                k = (len(sorted_vals) - 1) * 0.95
                f = math.floor(k)
                c = math.ceil(k)
                observed = sorted_vals[int(k)] if f == c else (sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f))
            else:
                observed = None

        elif rule.metric == "cost":
            trace_ids = [t.trace_id for t in traces]
            if trace_ids:
                stmt_spans = select(Span.estimated_cost).where(Span.trace_id.in_(trace_ids))
                res_spans = await session.execute(stmt_spans)
                observed = sum(float(c) for c in res_spans.scalars().all() if c is not None)
            else:
                observed = 0.0

        elif rule.metric == "token_usage":
            trace_ids = [t.trace_id for t in traces]
            if trace_ids:
                stmt_spans = select(Span.total_tokens).where(Span.trace_id.in_(trace_ids))
                res_spans = await session.execute(stmt_spans)
                observed = sum(t for t in res_spans.scalars().all() if t is not None)
            else:
                observed = 0.0

        elif rule.metric == "quality_score":
            scores = [t.quality_score for t in traces if t.quality_score is not None]
            observed = (sum(scores) / len(scores)) if scores else None

        if observed is None:
            # Not enough data to evaluate this rule, skip
            continue

        # 4. Perform operator check
        crossed = False
        op = rule.operator
        if op == ">":
            crossed = observed > rule.threshold
        elif op == "<":
            crossed = observed < rule.threshold
        elif op == ">=":
            crossed = observed >= rule.threshold
        elif op == "<=":
            crossed = observed <= rule.threshold
        elif op == "==":
            crossed = observed == rule.threshold

        # 5. Fetch current active incident (Alert) for this rule
        stmt_alert = select(Alert).where(
            and_(
                Alert.alert_rule_id == rule.id,
                Alert.status.in_(["TRIGGERED", "ACKNOWLEDGED"])
            )
        )
        res_alert = await session.execute(stmt_alert)
        active_alert = res_alert.scalar_one_or_none()

        if crossed:
            if active_alert:
                # Deduplication: Update existing alert
                active_alert.last_seen_at = datetime.now(UTC)
                active_alert.occurrence_count += 1
                active_alert.observed_value = observed
            else:
                # Trigger a new Alert incident
                triggered_count += 1
                new_alert = Alert(
                    id=None,  # Auto UUID
                    alert_rule_id=rule.id,
                    project_id=rule.project_id,
                    status="TRIGGERED",
                    severity=rule.severity,
                    message=f"Alert rule '{rule.name}' triggered: {rule.metric} is {observed:.4f} (threshold {rule.operator} {rule.threshold:.4f})",
                    observed_value=observed,
                    occurrence_count=1,
                    triggered_at=datetime.now(UTC),
                    last_seen_at=datetime.now(UTC),
                )
                session.add(new_alert)
                await session.flush()  # Assign UUID

                # Track Prometheus metrics
                from app.core.metrics import airex_alerts_triggered_total
                airex_alerts_triggered_total.labels(metric=rule.metric, severity=rule.severity).inc()

                # Dispatch Notification (Webhook)
                if webhook_url:
                    provider = WebhookNotificationProvider(webhook_url)
                    payload = {
                        "alert_id": str(new_alert.id),
                        "severity": rule.severity,
                        "metric": rule.metric,
                        "threshold": rule.threshold,
                        "observed": observed,
                        "status": "TRIGGERED",
                        "project_id": str(rule.project_id),
                        "message": new_alert.message,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    try:
                        await provider.send_notification(payload, webhook_secret)
                        new_alert.notification_status = "SENT"
                        from app.core.metrics import airex_notifications_sent_total
                        airex_notifications_sent_total.labels(channel="webhook").inc()
                    except Exception as e:
                        new_alert.notification_status = "FAILED"
                        new_alert.notification_error = str(e)
                        from app.core.metrics import airex_notifications_failed_total
                        airex_notifications_failed_total.labels(channel="webhook").inc()

        else:
            # Condition is normal
            if active_alert:
                # Transition TRIGGERED -> RESOLVED (Recovery)
                resolved_count += 1
                active_alert.status = "RESOLVED"
                active_alert.resolved_at = datetime.now(UTC)

                # Track Prometheus metrics
                from app.core.metrics import airex_alerts_resolved_total
                airex_alerts_resolved_total.labels(metric=rule.metric).inc()

                # Dispatch Notification (Webhook Resolution)
                if webhook_url:
                    provider = WebhookNotificationProvider(webhook_url)
                    payload = {
                        "alert_id": str(active_alert.id),
                        "severity": rule.severity,
                        "metric": rule.metric,
                        "threshold": rule.threshold,
                        "observed": observed,
                        "status": "RESOLVED",
                        "project_id": str(rule.project_id),
                        "message": f"Alert rule '{rule.name}' has resolved. Metric returned to normal: {observed:.4f}",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                    try:
                        await provider.send_notification(payload, webhook_secret)
                        from app.core.metrics import airex_notifications_sent_total
                        airex_notifications_sent_total.labels(channel="webhook").inc()
                    except Exception as e:
                        logger.error(f"Failed to dispatch resolution webhook: {e}")

    await session.commit()
    return {
        "evaluated_rules": evaluated_count,
        "triggered_alerts": triggered_count,
        "resolved_alerts": resolved_count,
    }
