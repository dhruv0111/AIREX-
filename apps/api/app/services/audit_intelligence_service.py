"""Audit Intelligence & Unified Timeline Service (spec Phase 14)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


class AuditIntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def query_timeline(
        self,
        organization_id: UUID,
        project_id: UUID | None = None,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        category: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query unified audit events with multi-dimensional filtering."""
        stmt = select(AuditLog).where(AuditLog.organization_id == organization_id)

        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)

        stmt = stmt.order_by(AuditLog.created_at.desc())

        res = await self.session.execute(stmt)
        all_logs = list(res.scalars().all())

        # Collect user names for actor attribution
        user_ids = {log.user_id for log in all_logs if log.user_id}
        user_map: dict[UUID, str] = {}
        if user_ids:
            u_stmt = select(User).where(User.id.in_(user_ids))
            u_res = await self.session.execute(u_stmt)
            for u in u_res.scalars().all():
                user_map[u.id] = u.name

        items = []
        for log in all_logs:
            # Derive event category from action prefix
            action_parts = log.action.split(".", 1)
            derived_cat = action_parts[0].upper() if len(action_parts) > 1 else "GENERAL"

            if category and derived_cat != category.upper():
                continue

            # Derive severity
            severity = "INFO"
            if any(term in log.action for term in ("failed", "rejected", "blocked", "tampered", "violation")):
                severity = "ERROR"
            elif any(term in log.action for term in ("warn", "stale", "revoked", "expired")):
                severity = "WARNING"

            items.append({
                "id": log.id,
                "timestamp": log.created_at,
                "category": derived_cat,
                "action": log.action,
                "actor_id": log.user_id,
                "actor_name": user_map.get(log.user_id, "System / Automated"),
                "organization_id": log.organization_id,
                "project_id": project_id,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "severity": severity,
                "metadata": log.metadata_,
            })

        total = len(items)
        paginated = items[offset : offset + limit]
        return paginated, total
