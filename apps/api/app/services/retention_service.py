"""Centralized Retention & Legal Hold Service (spec Phase 14)."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailure
from app.models.compliance import RetentionPolicy, LegalHold
from app.models.trace import Trace, Span
from app.models.evaluation import EvaluationRun
from app.models.agent import AgentRun, AgentTrajectoryStep
from app.models.generation import GeneratedCandidate
from app.models.audit import AuditLog
from app.repositories.audit import AuditRepository


class RetentionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    # --- Retention Policies ---

    async def create_policy(
        self,
        organization_id: UUID,
        resource_type: str,
        retention_days: int,
        description: str | None = None,
    ) -> RetentionPolicy:
        if retention_days <= 0:
            raise ValidationFailure("retention_days must be positive.")

        # Check existing policy to increment version
        stmt = select(RetentionPolicy).where(
            RetentionPolicy.organization_id == organization_id,
            RetentionPolicy.resource_type == resource_type,
        ).order_by(RetentionPolicy.policy_version.desc())
        res = await self.session.execute(stmt)
        latest = res.scalar_one_or_none()

        version = (latest.policy_version + 1) if latest else 1

        # Deactivate old policies
        if latest and latest.is_active:
            latest.is_active = False

        now = datetime.now(UTC)
        policy = RetentionPolicy(
            organization_id=organization_id,
            resource_type=resource_type,
            retention_days=retention_days,
            policy_version=version,
            is_active=True,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self.session.add(policy)
        await self.session.flush()

        await self.audit.record(
            action="retention.policy_created",
            organization_id=organization_id,
            resource_type="retention_policy",
            resource_id=policy.id,
            metadata={"resource_type": resource_type, "retention_days": retention_days, "version": version},
        )
        return policy

    async def list_policies(self, organization_id: UUID) -> list[RetentionPolicy]:
        stmt = select(RetentionPolicy).where(
            RetentionPolicy.organization_id == organization_id,
            RetentionPolicy.is_active == True,
        ).order_by(RetentionPolicy.resource_type.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Legal Holds ---

    async def create_legal_hold(
        self,
        organization_id: UUID,
        title: str,
        resource_type: str,
        target_resource_id: str,
        reason: str | None = None,
        placed_by_id: UUID | None = None,
    ) -> LegalHold:
        now = datetime.now(UTC)
        hold = LegalHold(
            organization_id=organization_id,
            title=title,
            reason=reason,
            resource_type=resource_type,
            target_resource_id=target_resource_id,
            is_active=True,
            placed_by_id=placed_by_id,
            created_at=now,
        )
        self.session.add(hold)
        await self.session.flush()

        await self.audit.record(
            action="legal_hold.created",
            organization_id=organization_id,
            user_id=placed_by_id,
            resource_type="legal_hold",
            resource_id=hold.id,
            metadata={"title": title, "resource_type": resource_type, "target_resource_id": target_resource_id},
        )
        return hold

    async def release_legal_hold(
        self,
        organization_id: UUID,
        hold_id: UUID,
        released_by_id: UUID | None = None,
    ) -> LegalHold:
        stmt = select(LegalHold).where(
            LegalHold.id == hold_id,
            LegalHold.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        hold = res.scalar_one_or_none()
        if not hold:
            raise NotFoundError(f"Legal hold {hold_id} not found.")

        if not hold.is_active:
            raise ValidationFailure(f"Legal hold {hold_id} is already released.")

        hold.is_active = False
        hold.released_at = datetime.now(UTC)
        hold.released_by_id = released_by_id
        await self.session.flush()

        await self.audit.record(
            action="legal_hold.released",
            organization_id=organization_id,
            user_id=released_by_id,
            resource_type="legal_hold",
            resource_id=hold.id,
            metadata={"title": hold.title, "target_resource_id": hold.target_resource_id},
        )
        return hold

    async def list_legal_holds(
        self, organization_id: UUID, active_only: bool = True
    ) -> list[LegalHold]:
        stmt = select(LegalHold).where(LegalHold.organization_id == organization_id)
        if active_only:
            stmt = stmt.where(LegalHold.is_active == True)
        stmt = stmt.order_by(LegalHold.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def is_under_legal_hold(
        self, organization_id: UUID, resource_type: str, target_resource_id: str
    ) -> bool:
        """Check if a specific resource is locked under an active legal hold."""
        stmt = select(LegalHold).where(
            LegalHold.organization_id == organization_id,
            LegalHold.resource_type == resource_type,
            LegalHold.is_active == True,
            (LegalHold.target_resource_id == target_resource_id) | (LegalHold.target_resource_id == "*"),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None

    # --- Retention Execution & Preview ---

    async def execute_retention_cleanup(
        self,
        organization_id: UUID,
        dry_run: bool = True,
        resource_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Execute retention cleanup or return preview.
        Honors all active LegalHolds: resources under active legal hold are NEVER deleted.
        """
        policies = await self.list_policies(organization_id)
        active_holds = await self.list_legal_holds(organization_id, active_only=True)
        
        held_ids: dict[str, set[str]] = {}
        for h in active_holds:
            held_ids.setdefault(h.resource_type, set()).add(h.target_resource_id)

        now = datetime.now(UTC)
        total_scanned = 0
        total_eligible = 0
        total_protected = 0
        total_deleted = 0
        details: dict[str, int] = {}

        for pol in policies:
            if resource_types and pol.resource_type not in resource_types:
                continue

            cutoff = now - timedelta(days=pol.retention_days)
            type_held = held_ids.get(pol.resource_type, set())
            wildcard_held = "*" in type_held

            # 1. Traces
            if pol.resource_type in ("traces", "trace"):
                stmt = select(Trace.id).where(
                    Trace.created_at < cutoff,
                )
                res = await self.session.execute(stmt)
                candidate_ids = [str(t) for t in res.scalars().all()]
                total_scanned += len(candidate_ids)

                eligible = []
                for cid in candidate_ids:
                    if wildcard_held or cid in type_held:
                        total_protected += 1
                    else:
                        eligible.append(UUID(cid))

                total_eligible += len(eligible)
                if not dry_run and eligible:
                    # Delete spans first, then traces
                    await self.session.execute(delete(Span).where(Span.trace_id.in_(eligible)))
                    await self.session.execute(delete(Trace).where(Trace.id.in_(eligible)))
                    total_deleted += len(eligible)
                details[pol.resource_type] = len(eligible)

            # 2. Generated Candidates
            elif pol.resource_type in ("candidates", "generated_candidates"):
                stmt = select(GeneratedCandidate.id).where(
                    GeneratedCandidate.created_at < cutoff,
                )
                res = await self.session.execute(stmt)
                candidate_ids = [str(c) for c in res.scalars().all()]
                total_scanned += len(candidate_ids)

                eligible = []
                for cid in candidate_ids:
                    if wildcard_held or cid in type_held:
                        total_protected += 1
                    else:
                        eligible.append(UUID(cid))

                total_eligible += len(eligible)
                if not dry_run and eligible:
                    await self.session.execute(
                        delete(GeneratedCandidate).where(GeneratedCandidate.id.in_(eligible))
                    )
                    total_deleted += len(eligible)
                details[pol.resource_type] = len(eligible)

            else:
                details[pol.resource_type] = 0

        if not dry_run:
            await self.session.flush()
            await self.audit.record(
                action="retention.cleanup_executed",
                organization_id=organization_id,
                metadata={
                    "total_deleted": total_deleted,
                    "protected_by_legal_hold": total_protected,
                    "details": details,
                },
            )

        return {
            "dry_run": dry_run,
            "scanned_records": total_scanned,
            "eligible_for_deletion": total_eligible,
            "protected_by_legal_hold": total_protected,
            "deleted_records": total_deleted,
            "details": details,
        }
