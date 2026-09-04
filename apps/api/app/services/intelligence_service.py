"""Intelligence service for release decisions, health overviews, and comparisons (Phase 10)."""

from __future__ import annotations

import time
from datetime import datetime, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailure
from app.models.project import Project, Environment
from app.models.provider import Model, Provider
from app.models.release_decision import (
    ReleasePolicy,
    ReleaseDecision,
    ReleaseEvidence,
    ReleaseCheck,
)
from app.repositories.audit import AuditRepository
from app.repositories.release_decision import ReleaseDecisionRepository
from app.services.decision_engine import DecisionEngine
from app.services.evidence_aggregator import EvidenceAggregator
from app.services.fingerprint import compute_configuration_fingerprint
from app.core import metrics


class IntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ReleaseDecisionRepository(session)
        self._audit = AuditRepository(session)

    # ------------------------------------------------------------- Policy Operations
    async def create_policy(
        self,
        *,
        project_id: UUID,
        user_id: UUID,
        name: str,
        description: str | None = None,
        environment_id: UUID | None = None,
        **rule_kwargs: Any,
    ) -> ReleasePolicy:
        policy = await self._repo.create_policy(
            project_id=project_id,
            environment_id=environment_id,
            name=name,
            description=description,
            created_by=user_id,
            **rule_kwargs,
        )
        await self._audit.record(
            action="RELEASE_POLICY_CREATED",
            organization_id=None,
            user_id=user_id,
            resource_type="release_policy",
            resource_id=policy.id,
            metadata={"name": name, "project_id": str(project_id), "version": policy.version},
        )
        return policy

    async def update_policy(
        self,
        *,
        policy_id: UUID,
        user_id: UUID,
        **updates: Any,
    ) -> ReleasePolicy:
        policy = await self._repo.get_policy_by_id(policy_id)
        if not policy:
            raise NotFoundError("Release policy not found.")

        updated = await self._repo.update_policy(policy, **updates)
        await self._audit.record(
            action="RELEASE_POLICY_UPDATED",
            organization_id=None,
            user_id=user_id,
            resource_type="release_policy",
            resource_id=policy.id,
            metadata={"name": policy.name, "version": updated.version},
        )
        return updated

    # ------------------------------------------------------------- Decision Operations
    async def create_decision(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        environment_id: UUID,
        model_id: UUID,
        release_policy_id: UUID,
        user_id: UUID,
        model_version: str | None = None,
        model_configuration: dict[str, Any] | None = None,
    ) -> ReleaseDecision:
        policy = await self._repo.get_policy_by_id(release_policy_id)
        if not policy or policy.project_id != project_id:
            raise NotFoundError("Release policy not found in project.")

        model = await self._session.get(Model, model_id)
        if not model or model.project_id != project_id:
            raise NotFoundError("Model not found in project.")

        fingerprint = compute_configuration_fingerprint(
            model_id=model_id,
            provider_id=model.provider_id,
            environment_id=environment_id,
            model_version=model_version or model.model_identifier,
            model_configuration=model_configuration or model.configuration,
            policy_version=policy.version,
        )

        decision = await self._repo.create_decision(
            project_id=project_id,
            organization_id=organization_id,
            environment_id=environment_id,
            model_id=model_id,
            provider_id=model.provider_id,
            release_policy_id=release_policy_id,
            policy_version=policy.version,
            configuration_fingerprint=fingerprint,
            model_version=model_version,
            model_configuration=model_configuration,
            created_by=user_id,
        )

        await self._audit.record(
            action="RELEASE_DECISION_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="release_decision",
            resource_id=decision.id,
            metadata={
                "project_id": str(project_id),
                "model_id": str(model_id),
                "environment_id": str(environment_id),
            },
        )
        return decision

    async def evaluate_decision(
        self,
        decision_id: UUID,
        user_id: UUID | None = None,
    ) -> ReleaseDecision:
        start_time = time.perf_counter()

        decision = await self._repo.get_decision_by_id(decision_id)
        if not decision:
            raise NotFoundError("Release decision not found.")

        policy = await self._repo.get_policy_by_id(decision.release_policy_id)
        if not policy:
            raise NotFoundError("Release policy not found for decision.")

        # Update status to COLLECTING_EVIDENCE
        decision.status = "COLLECTING_EVIDENCE"
        await self._session.flush()

        # Aggregate evidence
        aggregator = EvidenceAggregator(self._session)
        evidences_data = await aggregator.aggregate(
            project_id=decision.project_id,
            environment_id=decision.environment_id,
            model_id=decision.model_id,
            provider_id=decision.provider_id,
            max_age_days=policy.max_evidence_age_days,
        )

        # Clear prior evidences/checks if re-evaluating
        decision.evidences.clear()
        decision.checks.clear()
        await self._session.flush()

        # Save aggregated evidences
        await self._repo.add_evidences(decision.id, evidences_data)

        # Evaluate checks with Decision Engine
        engine = DecisionEngine(policy)
        result = engine.evaluate(
            evidences_data,
            model_id=decision.model_id,
            environment_id=decision.environment_id,
        )

        # Save checks
        await self._repo.add_checks(decision.id, result["checks"])

        # Update decision object
        decision.status = "DECIDED"
        decision.outcome = result["outcome"]
        decision.readiness_score = result["readiness_score"]
        decision.readiness_breakdown = {
            "dimensions": result["readiness_breakdown"],
            "recommendations": result["recommendations"],
        }
        decision.evaluated_at = datetime.now(UTC)
        decision.policy_version = policy.version
        await self._session.flush()

        # Mark previous decisions as SUPERSEDED
        await self._repo.mark_superseded(
            project_id=decision.project_id,
            environment_id=decision.environment_id,
            model_id=decision.model_id,
            new_decision_id=decision.id,
        )

        # Audit event
        audit_action = f"RELEASE_DECISION_{decision.outcome}"
        await self._audit.record(
            action=audit_action,
            organization_id=decision.organization_id,
            user_id=user_id or decision.created_by,
            resource_type="release_decision",
            resource_id=decision.id,
            metadata={
                "outcome": decision.outcome,
                "readiness_score": decision.readiness_score,
                "project_id": str(decision.project_id),
            },
        )

        # Metrics
        duration = time.perf_counter() - start_time
        env_obj = await self._session.get(Environment, decision.environment_id)
        env_name = env_obj.name if env_obj else "unknown"
        if hasattr(metrics, "airex_release_decisions_total"):
            metrics.airex_release_decisions_total.labels(
                outcome=decision.outcome,
                environment=env_name,
            ).inc()
            metrics.airex_release_decision_duration_seconds.observe(duration)
            for c in result["checks"]:
                metrics.airex_release_decision_checks_total.labels(
                    rule=c["rule_name"],
                    status=c["status"],
                ).inc()
            if decision.outcome == "BLOCKED":
                metrics.airex_release_decision_blocked_total.labels(
                    reason=result["checks"][0]["rule_name"] if result["checks"] else "unknown"
                ).inc()

        # Reload full decision with relationships
        return await self._repo.get_decision_by_id(decision.id)

    # ------------------------------------------------------------- Decision Comparison
    async def compare_decisions(
        self,
        current_id: UUID,
        previous_id: UUID | None = None,
    ) -> dict[str, Any]:
        current = await self._repo.get_decision_by_id(current_id)
        if not current:
            raise NotFoundError("Current decision not found.")

        previous: ReleaseDecision | None = None
        if previous_id:
            previous = await self._repo.get_decision_by_id(previous_id)
        else:
            previous = await self._repo.get_previous_decided(current)

        if not previous:
            return {
                "current_decision_id": current.id,
                "previous_decision_id": current.id,
                "is_compatible": True,
                "metrics": [],
                "summary": "No previous decision available for baseline comparison.",
            }

        # Check compatibility: same model and environment
        is_compatible = (
            current.model_id == previous.model_id
            and current.environment_id == previous.environment_id
        )

        metrics_diff: list[dict[str, Any]] = []

        # 1. Readiness Score
        curr_score = current.readiness_score or 0.0
        prev_score = previous.readiness_score or 0.0
        score_diff = curr_score - prev_score
        status = "UNCHANGED" if abs(score_diff) < 0.1 else ("IMPROVED" if score_diff > 0 else "REGRESSED")
        metrics_diff.append({
            "metric_name": "Readiness Score",
            "dimension": "General",
            "previous_value": prev_score,
            "current_value": curr_score,
            "change_status": status,
            "explanation": f"Readiness score shifted by {score_diff:+.1f} points.",
        })

        # 2. Extract benchmark reliability score comparison
        curr_bench = next((e for e in current.evidences if e.source_type == "BENCHMARK"), None)
        prev_bench = next((e for e in previous.evidences if e.source_type == "BENCHMARK"), None)
        curr_rel = curr_bench.summary.get("reliability_score") if curr_bench and curr_bench.summary else None
        prev_rel = prev_bench.summary.get("reliability_score") if prev_bench and prev_bench.summary else None
        if curr_rel is not None and prev_rel is not None:
            rel_diff = curr_rel - prev_rel
            rel_status = "UNCHANGED" if abs(rel_diff) < 0.1 else ("IMPROVED" if rel_diff > 0 else "REGRESSED")
            metrics_diff.append({
                "metric_name": "Benchmark Reliability",
                "dimension": "Reliability",
                "previous_value": prev_rel,
                "current_value": curr_rel,
                "change_status": rel_status,
                "explanation": f"Benchmark reliability score shifted by {rel_diff:+.1f}%.",
            })

        # 3. Observability Error Rate
        curr_obs = next((e for e in current.evidences if e.source_type == "OBSERVABILITY"), None)
        prev_obs = next((e for e in previous.evidences if e.source_type == "OBSERVABILITY"), None)
        curr_err = curr_obs.summary.get("error_rate") if curr_obs and curr_obs.summary else None
        prev_err = prev_obs.summary.get("error_rate") if prev_obs and prev_obs.summary else None
        if curr_err is not None and prev_err is not None:
            err_diff = curr_err - prev_err
            # lower error rate is IMPROVED
            err_status = "UNCHANGED" if abs(err_diff) < 0.001 else ("IMPROVED" if err_diff < 0 else "REGRESSED")
            metrics_diff.append({
                "metric_name": "Error Rate",
                "dimension": "Observability",
                "previous_value": f"{prev_err * 100:.2f}%",
                "current_value": f"{curr_err * 100:.2f}%",
                "change_status": err_status,
                "explanation": f"Error rate shifted by {err_diff * 100:+.2f}%.",
            })

        # 4. Latency P95
        curr_p95 = curr_obs.summary.get("p95_latency_ms") if curr_obs and curr_obs.summary else None
        prev_p95 = prev_obs.summary.get("p95_latency_ms") if prev_obs and prev_obs.summary else None
        if curr_p95 is not None and prev_p95 is not None:
            p95_diff = curr_p95 - prev_p95
            p95_status = "UNCHANGED" if abs(p95_diff) < 5.0 else ("IMPROVED" if p95_diff < 0 else "REGRESSED")
            metrics_diff.append({
                "metric_name": "P95 Latency",
                "dimension": "Performance",
                "previous_value": f"{prev_p95:.1f}ms",
                "current_value": f"{curr_p95:.1f}ms",
                "change_status": p95_status,
                "explanation": f"P95 latency changed by {p95_diff:+.1f}ms.",
            })

        # 5. Regression state
        curr_exp = next((e for e in current.evidences if e.source_type == "EXPERIMENT"), None)
        prev_exp = next((e for e in previous.evidences if e.source_type == "EXPERIMENT"), None)
        curr_sev = curr_exp.summary.get("max_regression_severity", "NONE") if curr_exp and curr_exp.summary else "NONE"
        prev_sev = prev_exp.summary.get("max_regression_severity", "NONE") if prev_exp and prev_exp.summary else "NONE"
        sev_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        c_rank = sev_rank.get(curr_sev.upper(), 0)
        p_rank = sev_rank.get(prev_sev.upper(), 0)
        reg_status = "UNCHANGED" if c_rank == p_rank else ("IMPROVED" if c_rank < p_rank else "REGRESSED")
        metrics_diff.append({
            "metric_name": "Regression Severity",
            "dimension": "Safety",
            "previous_value": prev_sev,
            "current_value": curr_sev,
            "change_status": reg_status,
            "explanation": f"Regression severity changed from {prev_sev} to {curr_sev}.",
        })

        summary = (
            f"Compared Decision {current.id} against prior Decision {previous.id}. "
            f"Overall readiness score: {prev_score:.1f} → {curr_score:.1f} ({score_diff:+.1f})."
        )

        return {
            "current_decision_id": current.id,
            "previous_decision_id": previous.id,
            "is_compatible": is_compatible,
            "metrics": metrics_diff,
            "summary": summary,
        }

    # ------------------------------------------------------------- Executive Health Overview
    async def get_project_overview(self, project_id: UUID) -> dict[str, Any]:
        latest_dec = await self._repo.get_latest_decided(project_id)

        blocking_issues: list[str] = []
        warnings: list[str] = []

        overall_status = "READY"
        if not latest_dec:
            overall_status = "INSUFFICIENT_EVIDENCE"
            blocking_issues.append("No release decision has been evaluated yet for this project.")
        else:
            if latest_dec.outcome == "BLOCKED":
                overall_status = "BLOCKED"
                blocking_issues.extend(
                    c.explanation for c in latest_dec.checks if c.status in ("FAIL", "MISSING") and c.is_blocking
                )
            elif latest_dec.outcome in ("REJECTED", "INSUFFICIENT_EVIDENCE"):
                overall_status = "AT_RISK" if latest_dec.outcome == "REJECTED" else "INSUFFICIENT_EVIDENCE"
                blocking_issues.extend(
                    c.explanation for c in latest_dec.checks if c.status in ("FAIL", "MISSING")
                )
            elif latest_dec.outcome == "CONDITIONALLY_APPROVED":
                overall_status = "AT_RISK"
                warnings.extend(
                    c.explanation for c in latest_dec.checks if c.status in ("WARNING", "STALE")
                )

        # Model comparisons: query models in project and extract available metrics
        model_stmt = select(Model).where(Model.project_id == project_id)
        model_res = await self._session.execute(model_stmt)
        models = list(model_res.scalars().all())

        model_comparisons: list[dict[str, Any]] = []
        for m in models:
            latest_m_dec = await self._repo.get_latest_decided(project_id, model_id=m.id)
            score = latest_m_dec.readiness_score if latest_m_dec else None
            outcome = latest_m_dec.outcome if latest_m_dec else "NO_DECISION"
            model_comparisons.append({
                "model_id": str(m.id),
                "name": m.name,
                "provider_id": str(m.provider_id),
                "readiness_score": score,
                "latest_outcome": outcome,
            })

        # Recent changes feed
        decisions_list = await self._repo.list_decisions_by_project(project_id)
        recent_changes: list[dict[str, Any]] = [
            {
                "decision_id": str(d.id),
                "model_id": str(d.model_id),
                "outcome": d.outcome,
                "status": d.status,
                "readiness_score": d.readiness_score,
                "created_at": d.created_at.isoformat(),
            }
            for d in decisions_list[:5]
        ]

        return {
            "project_id": project_id,
            "overall_status": overall_status,
            "readiness_score": latest_dec.readiness_score if latest_dec else None,
            "latest_decision": latest_dec,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
            "model_comparisons": model_comparisons,
            "recent_changes": recent_changes,
        }

    # ------------------------------------------------------------- Required Actions
    async def get_project_actions(self, project_id: UUID) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        latest_dec = await self._repo.get_latest_decided(project_id)

        if not latest_dec:
            actions.append({
                "action_type": "CREATE_DECISION",
                "priority": "HIGH",
                "title": "Configure Release Policy & Decision",
                "description": "Establish a deployment release policy and trigger the first evaluation.",
            })
            actions.append({
                "action_type": "RUN_BENCHMARK",
                "priority": "MEDIUM",
                "title": "Execute Benchmark Suite",
                "description": "Generate baseline empirical reliability score.",
            })
            return actions

        for c in latest_dec.checks:
            if c.status == "MISSING" and c.rule_name == "required_benchmark":
                actions.append({
                    "action_type": "RUN_BENCHMARK",
                    "priority": "CRITICAL",
                    "title": "Run Benchmark Suite",
                    "description": "A completed benchmark run is required to satisfy deployment policy.",
                })
            elif c.status == "MISSING" and c.rule_name == "required_evaluation":
                actions.append({
                    "action_type": "RUN_EVALUATION",
                    "priority": "CRITICAL",
                    "title": "Execute Evaluation Run",
                    "description": "An evaluation run across the test dataset is required.",
                })
            elif c.status == "FAIL" and c.rule_name == "critical_alerts":
                actions.append({
                    "action_type": "RESOLVE_ALERT",
                    "priority": "BLOCKING",
                    "title": "Remediate Active Critical Alert",
                    "description": "Resolve active critical alert incident before deployment.",
                })
            elif c.status == "STALE":
                actions.append({
                    "action_type": "REFRESH_EVIDENCE",
                    "priority": "MEDIUM",
                    "title": f"Refresh Stale Evidence ({c.rule_name})",
                    "description": "Evidence is older than policy expiration; trigger a new run.",
                })

        if not actions:
            actions.append({
                "action_type": "NONE",
                "priority": "LOW",
                "title": "System All Clear",
                "description": "All policy rules satisfied. Model is ready for deployment.",
            })

        return actions
