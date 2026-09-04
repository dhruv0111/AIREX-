"""Repository for Phase 10 Release Policies, Decisions, Evidence, and Checks."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select, update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.release_decision import (
    ReleasePolicy,
    ReleaseDecision,
    ReleaseEvidence,
    ReleaseCheck,
)


class ReleaseDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- Policies
    async def create_policy(
        self,
        *,
        project_id: UUID,
        environment_id: UUID | None,
        name: str,
        description: str | None,
        created_by: UUID | None,
        min_reliability_score: float | None = None,
        max_regression_severity: str | None = None,
        max_error_rate: float | None = None,
        max_latency_ms: float | None = None,
        max_p95_latency_ms: float | None = None,
        max_cost: float | None = None,
        max_critical_alerts: int = 0,
        min_statistical_confidence: float | None = None,
        min_sample_size: int | None = None,
        required_benchmark: bool = False,
        required_evaluation: bool = False,
        required_dataset_version_id: UUID | None = None,
        required_quality_gates: bool = False,
        max_evidence_age_days: int = 14,
        custom_rules: dict[str, Any] | None = None,
    ) -> ReleasePolicy:
        policy = ReleasePolicy(
            project_id=project_id,
            environment_id=environment_id,
            name=name,
            description=description,
            created_by=created_by,
            min_reliability_score=min_reliability_score,
            max_regression_severity=max_regression_severity,
            max_error_rate=max_error_rate,
            max_latency_ms=max_latency_ms,
            max_p95_latency_ms=max_p95_latency_ms,
            max_cost=max_cost,
            max_critical_alerts=max_critical_alerts,
            min_statistical_confidence=min_statistical_confidence,
            min_sample_size=min_sample_size,
            required_benchmark=required_benchmark,
            required_evaluation=required_evaluation,
            required_dataset_version_id=required_dataset_version_id,
            required_quality_gates=required_quality_gates,
            max_evidence_age_days=max_evidence_age_days,
            custom_rules=custom_rules,
            version=1,
        )
        self._session.add(policy)
        await self._session.flush()
        return policy

    async def get_policy_by_id(self, policy_id: UUID) -> ReleasePolicy | None:
        stmt = select(ReleasePolicy).where(ReleasePolicy.id == policy_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_policies_by_project(self, project_id: UUID) -> list[ReleasePolicy]:
        stmt = (
            select(ReleasePolicy)
            .where(ReleasePolicy.project_id == project_id)
            .order_by(desc(ReleasePolicy.created_at))
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def update_policy(
        self,
        policy: ReleasePolicy,
        **updates: Any,
    ) -> ReleasePolicy:
        for k, v in updates.items():
            if hasattr(policy, k) and v is not None:
                setattr(policy, k, v)
        policy.version += 1
        policy.updated_at = datetime.now(UTC)
        await self._session.flush()
        return policy

    # ------------------------------------------------------------- Decisions
    async def create_decision(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        environment_id: UUID,
        model_id: UUID,
        provider_id: UUID,
        release_policy_id: UUID,
        policy_version: int,
        configuration_fingerprint: str,
        model_version: str | None = None,
        model_configuration: dict[str, Any] | None = None,
        created_by: UUID | None = None,
    ) -> ReleaseDecision:
        decision = ReleaseDecision(
            project_id=project_id,
            organization_id=organization_id,
            environment_id=environment_id,
            model_id=model_id,
            provider_id=provider_id,
            release_policy_id=release_policy_id,
            policy_version=policy_version,
            model_version=model_version,
            model_configuration=model_configuration,
            configuration_fingerprint=configuration_fingerprint,
            status="DRAFT",
            outcome=None,
            created_by=created_by,
        )
        self._session.add(decision)
        await self._session.flush()
        loaded = await self.get_decision_by_id(decision.id)
        return loaded or decision

    async def get_decision_by_id(self, decision_id: UUID) -> ReleaseDecision | None:
        stmt = (
            select(ReleaseDecision)
            .where(ReleaseDecision.id == decision_id)
            .options(
                selectinload(ReleaseDecision.checks),
                selectinload(ReleaseDecision.evidences),
            )
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_decisions_by_project(
        self,
        project_id: UUID,
        environment_id: UUID | None = None,
        model_id: UUID | None = None,
    ) -> list[ReleaseDecision]:
        stmt = (
            select(ReleaseDecision)
            .where(ReleaseDecision.project_id == project_id)
            .options(
                selectinload(ReleaseDecision.checks),
                selectinload(ReleaseDecision.evidences),
            )
            .order_by(desc(ReleaseDecision.created_at))
        )
        if environment_id:
            stmt = stmt.where(ReleaseDecision.environment_id == environment_id)
        if model_id:
            stmt = stmt.where(ReleaseDecision.model_id == model_id)

        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def get_latest_decided(
        self,
        project_id: UUID,
        environment_id: UUID | None = None,
        model_id: UUID | None = None,
    ) -> ReleaseDecision | None:
        stmt = (
            select(ReleaseDecision)
            .where(
                and_(
                    ReleaseDecision.project_id == project_id,
                    ReleaseDecision.status == "DECIDED",
                )
            )
            .options(
                selectinload(ReleaseDecision.checks),
                selectinload(ReleaseDecision.evidences),
            )
            .order_by(desc(ReleaseDecision.evaluated_at), desc(ReleaseDecision.created_at))
            .limit(1)
        )
        if environment_id:
            stmt = stmt.where(ReleaseDecision.environment_id == environment_id)
        if model_id:
            stmt = stmt.where(ReleaseDecision.model_id == model_id)

        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_previous_decided(
        self,
        current_decision: ReleaseDecision,
    ) -> ReleaseDecision | None:
        stmt = (
            select(ReleaseDecision)
            .where(
                and_(
                    ReleaseDecision.project_id == current_decision.project_id,
                    ReleaseDecision.environment_id == current_decision.environment_id,
                    ReleaseDecision.model_id == current_decision.model_id,
                    ReleaseDecision.id != current_decision.id,
                    ReleaseDecision.status.in_(["DECIDED", "SUPERSEDED", "STALE"]),
                    ReleaseDecision.outcome.isnot(None),
                )
            )
            .options(
                selectinload(ReleaseDecision.checks),
                selectinload(ReleaseDecision.evidences),
            )
            .order_by(desc(ReleaseDecision.evaluated_at), desc(ReleaseDecision.created_at))
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def add_evidences(
        self,
        decision_id: UUID,
        evidences_data: list[dict[str, Any]],
    ) -> list[ReleaseEvidence]:
        evidences = []
        for ev in evidences_data:
            obj = ReleaseEvidence(
                release_decision_id=decision_id,
                source_type=ev["source_type"],
                source_id=str(ev["source_id"]),
                environment_id=ev.get("environment_id"),
                methodology_version=ev.get("methodology_version"),
                freshness_timestamp=ev.get("freshness_timestamp"),
                is_fresh=ev.get("is_fresh", True),
                summary=ev.get("summary"),
            )
            self._session.add(obj)
            evidences.append(obj)
        await self._session.flush()
        return evidences

    async def add_checks(
        self,
        decision_id: UUID,
        checks_data: list[dict[str, Any]],
    ) -> list[ReleaseCheck]:
        checks = []
        for ck in checks_data:
            obj = ReleaseCheck(
                release_decision_id=decision_id,
                rule_name=ck["rule_name"],
                status=ck["status"],
                actual_value=ck.get("actual_value"),
                expected_value=ck.get("expected_value"),
                evidence_reference=ck.get("evidence_reference"),
                explanation=ck["explanation"],
                is_blocking=ck.get("is_blocking", False),
            )
            self._session.add(obj)
            checks.append(obj)
        await self._session.flush()
        return checks

    async def mark_superseded(
        self,
        *,
        project_id: UUID,
        environment_id: UUID,
        model_id: UUID,
        new_decision_id: UUID,
    ) -> int:
        stmt = (
            update(ReleaseDecision)
            .where(
                and_(
                    ReleaseDecision.project_id == project_id,
                    ReleaseDecision.environment_id == environment_id,
                    ReleaseDecision.model_id == model_id,
                    ReleaseDecision.id != new_decision_id,
                    ReleaseDecision.status.in_(["DECIDED", "READY"]),
                )
            )
            .values(
                status="SUPERSEDED",
                superseded_by_id=new_decision_id,
                updated_at=datetime.now(UTC),
            )
        )
        res = await self._session.execute(stmt)
        return res.rowcount
