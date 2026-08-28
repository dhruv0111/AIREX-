"""Alerts and Alert Rules API endpoints (Phase 8)."""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.errors import ForbiddenError, NotFoundError, ValidationFailure
from app.core.permissions import Role
from app.db.session import get_db
from app.models.user import User
from app.models.project import Project
from app.models.alert import AlertRule, Alert
from app.schemas.alert import AlertRuleCreate, AlertRuleUpdate
from app.services.organization import OrganizationService

router = APIRouter()


async def _verify_project_access(project_id: UUID, user_id: UUID, db: AsyncSession, require_write: bool = False) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise NotFoundError("Project not found.")

    org_service = OrganizationService(db)
    role = await org_service.resolve_membership(
        org_id=project.organization_id,
        user_id=user_id,
    )
    if role is None:
        raise ForbiddenError("You do not have access to this organization.")

    if require_write and role == Role.VIEWER:
        raise ForbiddenError("Viewer cannot perform write operations on alert rules.")

    return project


@router.get("/projects/{project_id}/alerts")
async def list_alerts(
    project_id: UUID,
    status: str | None = Query(None),
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all alerts for a project, optionally filtered by status."""
    await _verify_project_access(project_id, user.id, db)
    
    stmt = select(Alert).where(Alert.project_id == project_id)
    if status:
        stmt = stmt.where(Alert.status == status)
    
    stmt = stmt.order_by(Alert.triggered_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/projects/{project_id}/alerts/{alert_id}")
async def get_alert(
    project_id: UUID,
    alert_id: UUID,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed information for a single alert."""
    await _verify_project_access(project_id, user.id, db)
    
    stmt = select(Alert).where(
        and_(
            Alert.id == alert_id,
            Alert.project_id == project_id
        )
    )
    res = await db.execute(stmt)
    alert = res.scalar_one_or_none()
    if not alert:
        raise NotFoundError("Alert not found.")
    return alert


@router.post("/projects/{project_id}/alerts/{alert_id}/ack")
async def acknowledge_alert(
    project_id: UUID,
    alert_id: UUID,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge an active alert."""
    project = await _verify_project_access(project_id, user.id, db)

    stmt = select(Alert).where(
        and_(
            Alert.id == alert_id,
            Alert.project_id == project_id
        )
    )
    res = await db.execute(stmt)
    alert = res.scalar_one_or_none()
    if not alert:
        raise NotFoundError("Alert not found.")

    if alert.status in ("TRIGGERED", "ACKNOWLEDGED", "NORMAL"):
        if alert.status != "ACKNOWLEDGED":
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_at = datetime.now(UTC)
            alert.acknowledged_by = user.id

            # Log audit event
            from app.repositories.audit import AuditRepository
            audit = AuditRepository(db)
            await audit.record(
                action="ALERT_ACKNOWLEDGED",
                organization_id=project.organization_id,
                user_id=user.id,
                resource_type="alert",
                resource_id=alert_id,
                metadata={"alert_id": str(alert_id)},
            )

            await db.commit()

    return alert


@router.get("/projects/{project_id}/alert-rules")
async def list_alert_rules(
    project_id: UUID,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all alert rules configured for a project."""
    await _verify_project_access(project_id, user.id, db)
    
    stmt = select(AlertRule).where(AlertRule.project_id == project_id).order_by(AlertRule.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.post("/projects/{project_id}/alert-rules", status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    project_id: UUID,
    payload: AlertRuleCreate,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert rule."""
    project = await _verify_project_access(project_id, user.id, db, require_write=True)

    rule = AlertRule(
        id=uuid4(),
        project_id=project_id,
        name=payload.name,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        duration_seconds=payload.duration_seconds,
        cooldown_seconds=payload.cooldown_seconds,
        severity=payload.severity,
        environment=payload.environment,
        is_enabled=payload.is_enabled,
    )
    db.add(rule)

    # Log audit event
    from app.repositories.audit import AuditRepository
    audit = AuditRepository(db)
    await audit.record(
        action="ALERT_RULE_CREATED",
        organization_id=project.organization_id,
        user_id=user.id,
        resource_type="alert_rule",
        resource_id=rule.id,
        metadata={"name": payload.name, "metric": payload.metric},
    )

    await db.commit()
    return rule


@router.patch("/alert-rules/{id}")
async def update_alert_rule(
    id: UUID,
    payload: AlertRuleUpdate,
    request: Request,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing alert rule."""
    rule = await db.get(AlertRule, id)
    if not rule:
        raise NotFoundError("Alert rule not found.")

    # Multi-tenant and RBAC check
    project = await _verify_project_access(rule.project_id, user.id, db, require_write=True)

    update_data = payload.dict(exclude_unset=True)
    for key, val in update_data.items():
        setattr(rule, key, val)

    # Log audit event
    from app.repositories.audit import AuditRepository
    audit = AuditRepository(db)
    await audit.record(
        action="ALERT_RULE_UPDATED",
        organization_id=project.organization_id,
        user_id=user.id,
        resource_type="alert_rule",
        resource_id=id,
        metadata={"alert_rule_id": str(id), "updates": update_data},
    )

    await db.commit()
    return rule


@router.delete("/alert-rules/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    id: UUID,
    user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert rule."""
    rule = await db.get(AlertRule, id)
    if not rule:
        raise NotFoundError("Alert rule not found.")

    # Multi-tenant and RBAC check
    project = await _verify_project_access(rule.project_id, user.id, db, require_write=True)

    # Log audit event before deletion
    from app.repositories.audit import AuditRepository
    audit = AuditRepository(db)
    await audit.record(
        action="ALERT_RULE_DELETED",
        organization_id=project.organization_id,
        user_id=user.id,
        resource_type="alert_rule",
        resource_id=id,
        metadata={"alert_rule_id": str(id)},
    )

    await db.delete(rule)
    await db.commit()
