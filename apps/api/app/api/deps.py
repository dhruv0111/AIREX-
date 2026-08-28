"""API dependencies: authentication and organization resolution (spec §40–§41)."""

from __future__ import annotations

import hashlib
from datetime import datetime, UTC
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError, ForbiddenError, ValidationFailure
from app.core.logging import organization_id_ctx, user_id_ctx
from app.db.session import get_db
from app.models import User, Project
from app.models.ci import ServiceToken
from app.services.auth import AuthService
from app.services.organization import OrganizationService

_bearer = HTTPBearer(auto_error=False)

SCOPE_MAPPING = {
    # Experiments
    ("POST", "/api/v1/projects/{project_id}/experiments"): "experiments:write",
    ("GET", "/api/v1/projects/{project_id}/experiments"): "experiments:read",
    ("GET", "/api/v1/experiments/{experiment_id}"): "experiments:read",
    ("PATCH", "/api/v1/experiments/{experiment_id}"): "experiments:write",
    ("DELETE", "/api/v1/experiments/{experiment_id}"): "experiments:write",
    ("POST", "/api/v1/experiments/{experiment_id}/run"): "experiments:run",
    ("POST", "/api/v1/experiments/{id}/cancel"): "experiments:run",
    ("GET", "/api/v1/experiments/{experiment_id}/runs"): "experiments:read",
    ("GET", "/api/v1/experiments/{id}/results"): "experiments:read",
    ("GET", "/api/v1/experiments/{id}/comparison"): "experiments:read",
    ("GET", "/api/v1/experiments/{id}/regressions"): "experiments:read",
    ("GET", "/api/v1/experiments/{id}/quality-gates"): "experiments:read",
    
    # Datasets
    ("GET", "/api/v1/projects/{project_id}/datasets"): "datasets:read",
    
    # Models
    ("GET", "/api/v1/projects/{project_id}/models"): "models:read",
    
    # Evaluations
    ("POST", "/api/v1/projects/{project_id}/evaluations"): "experiments:run",
    ("GET", "/api/v1/projects/{project_id}/evaluations"): "experiments:read",
    ("GET", "/api/v1/evaluations/{id}"): "experiments:read",
    ("GET", "/api/v1/evaluations/{id}/results"): "experiments:read",
    
    # CI runs
    ("POST", "/api/v1/ci/runs"): "experiments:run",
    ("GET", "/api/v1/ci/runs/{id}"): "experiments:read",
    ("POST", "/api/v1/ci/runs/{id}/cancel"): "experiments:run",

    # Observability
    ("POST", "/api/v1/observability/ingest"): "experiments:run",
    ("GET", "/api/v1/projects/{project_id}/observability/overview"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/observability/traces"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/observability/models"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/observability/providers"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/observability/cost"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/observability/latency"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/observability/settings"): "experiments:read",
    ("PUT", "/api/v1/projects/{project_id}/observability/settings"): "experiments:write",
    ("GET", "/api/v1/observability/traces/{trace_id}"): "experiments:read",
    ("POST", "/api/v1/projects/{project_id}/observability/quality-signals"): "experiments:run",
    ("GET", "/api/v1/pricing"): "experiments:read",
    ("POST", "/api/v1/pricing"): "experiments:write",
    ("PATCH", "/api/v1/pricing/{pricing_id}"): "experiments:write",
    ("DELETE", "/api/v1/pricing/{pricing_id}"): "experiments:write",

    # Alerts
    ("GET", "/api/v1/projects/{project_id}/alerts"): "experiments:read",
    ("GET", "/api/v1/projects/{project_id}/alerts/{alert_id}"): "experiments:read",
    ("POST", "/api/v1/projects/{project_id}/alerts/{alert_id}/ack"): "experiments:write",
    ("GET", "/api/v1/projects/{project_id}/alert-rules"): "experiments:read",
    ("POST", "/api/v1/projects/{project_id}/alert-rules"): "experiments:write",
    ("PATCH", "/api/v1/alert-rules/{id}"): "experiments:write",
    ("DELETE", "/api/v1/alert-rules/{id}"): "experiments:write",
}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthError("Authentication required.")

    token_str = credentials.credentials
    # Check if this is a CI service token
    if token_str.startswith("airex_ci_"):
        token_hash = hashlib.sha256(token_str.encode()).hexdigest()
        stmt = select(ServiceToken).where(
            and_(
                ServiceToken.token_hash == token_hash,
                ServiceToken.revoked_at.is_(None)
            )
        )
        res = await session.execute(stmt)
        token = res.scalar_one_or_none()
        
        from app.core.metrics import service_token_auth_failures_total
        if not token:
            service_token_auth_failures_total.inc()
            raise AuthError("Invalid service token.")

        if token.expires_at:
            expires_at = token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < datetime.now(UTC):
                service_token_auth_failures_total.inc()
                raise AuthError("Service token has expired.")

        # Update last used
        token.last_used_at = datetime.now(UTC)

        # Resolve associated User (project creator or organization owner)
        project = await session.get(Project, token.project_id)
        if not project:
            service_token_auth_failures_total.inc()
            raise AuthError("Associated project not found.")

        user = None
        if project.created_by:
            user = await session.get(User, project.created_by)
        if not user:
            from app.models.organization import OrganizationMember
            from app.core.permissions import Role
            stmt_member = select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == token.organization_id,
                    OrganizationMember.role.in_([Role.OWNER, Role.ADMIN])
                )
            )
            res_member = await session.execute(stmt_member)
            member = res_member.scalars().first()
            if member:
                user = await session.get(User, member.user_id)
        if not user:
            service_token_auth_failures_total.inc()
            raise AuthError("No authorized user found for the token.")

        # Bind request context state
        request.state.is_service_token = True
        request.state.service_token_project_id = token.project_id
        request.state.service_token_scopes = token.scopes
        request.state.service_token_id = token.id

        # Enforce Scope limits
        route = request.scope.get("route")
        if route:
            path = route.path
            path_with_prefix = path if path.startswith("/api/v1") else f"/api/v1{path}"
            path_without_prefix = path[7:] if path.startswith("/api/v1") else path
            
            required_scope = None
            for p in (path_with_prefix, path_without_prefix):
                required_scope = SCOPE_MAPPING.get((request.method, p))
                if required_scope:
                    break
            
            if required_scope and required_scope not in token.scopes:
                raise ForbiddenError(f"Token lacks required scope: {required_scope}")

        # Enforce project boundary constraints on path parameters
        token_project_id = token.project_id
        path_project_id = request.path_params.get("project_id")
        if path_project_id:
            try:
                if UUID(path_project_id) != token_project_id:
                    raise ForbiddenError("Service token project boundary mismatch.")
            except ValueError:
                pass

        path_exp_id = request.path_params.get("experiment_id") or request.path_params.get("id")
        if path_exp_id:
            try:
                exp_uuid = UUID(path_exp_id)
                from app.models.experiment import Experiment, ExperimentRun
                exp = await session.get(Experiment, exp_uuid)
                if exp and exp.project_id != token_project_id:
                    raise ForbiddenError("Service token project boundary mismatch.")
                
                run = await session.get(ExperimentRun, exp_uuid)
                if run:
                    exp_from_run = await session.get(Experiment, run.experiment_id)
                    if exp_from_run and exp_from_run.project_id != token_project_id:
                        raise ForbiddenError("Service token project boundary mismatch.")
            except ValueError:
                pass

        path_eval_id = request.path_params.get("evaluation_id")
        if path_eval_id:
            try:
                eval_uuid = UUID(path_eval_id)
                from app.models.evaluation import EvaluationRun
                run = await session.get(EvaluationRun, eval_uuid)
                if run and run.project_id != token_project_id:
                    raise ForbiddenError("Service token project boundary mismatch.")
            except ValueError:
                pass

        user_id_ctx.set(str(user.id))
        return user

    # JWT user login logic
    service = AuthService(session)
    user = await service.user_from_token(token_str)
    user_id_ctx.set(str(user.id))
    return user


async def get_active_organization(
    request: Request,
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UUID:
    """Resolve the active organization from the header, validated by membership.

    A user must never gain access merely by changing the header (spec §41):
    membership is always validated server-side.
    """
    if getattr(request.state, "is_service_token", False):
        token_id = getattr(request.state, "service_token_id", None)
        token = await session.get(ServiceToken, token_id)
        if not token:
            raise ForbiddenError("Access denied.")
        organization_id_ctx.set(str(token.organization_id))
        return token.organization_id

    org_service = OrganizationService(session)
    if x_organization_id:
        try:
            org_id = UUID(x_organization_id)
        except ValueError:
            raise ValidationFailure("X-Organization-Id is not a valid UUID.")
        membership = await org_service.resolve_membership(org_id, user.id)
        if membership is None:
            raise ForbiddenError("You do not have access to this organization.")
        organization_id_ctx.set(str(org_id))
        return org_id

    memberships = await org_service.list_for_user(user.id)
    if not memberships:
        raise ForbiddenError("You do not belong to any organization.")
    if len(memberships) > 1:
        raise ValidationFailure("Multiple organizations found. Set the X-Organization-Id header.")
    organization_id_ctx.set(str(memberships[0].id))
    return memberships[0].id
