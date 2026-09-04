"""REST API router for Phase 11 AI Agent Evaluation, Trajectory Testing & Agent Reliability."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.errors import ForbiddenError, NotFoundError
from app.core.permissions import Role
from app.db.session import get_db
from app.models import OrganizationMember, Project, User
from app.schemas.agent import (
    AgentDefinitionCreate,
    AgentDefinitionResponse,
    AgentDefinitionUpdate,
    AgentRunCreate,
    AgentRunResponse,
    AgentTrajectoryStepResponse,
    ToolDefinitionCreate,
    ToolDefinitionResponse,
    TrajectoryEvaluationResponse,
)
from app.schemas.common import ok
from app.services.agent_service import AgentService

router = APIRouter(tags=["agents"])


async def _verify_project_access(
    project_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    session: AsyncSession,
    *,
    require_write: bool = False,
) -> Project:
    from app.core.permissions import resolve_user_project_access, Role
    from app.models.project import Project

    project = await session.get(Project, project_id)
    if not project or project.organization_id != organization_id:
        raise NotFoundError("Project not found.")

    role, access_type = await resolve_user_project_access(session, user_id, project_id, organization_id)
    if role is None:
        raise ForbiddenError("You do not have access to this project.")

    if require_write and role == Role.VIEWER:
        raise ForbiddenError("Read-only access: action requires member or admin role.")

    return project


# ------------------------------------------------------------- Tools Endpoints
@router.post("/projects/{project_id}/tools", status_code=http_status.HTTP_201_CREATED)
async def create_tool_definition(
    project_id: UUID,
    payload: ToolDefinitionCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = AgentService(session)
    tool = await service.create_tool(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        input_schema=payload.input_schema,
        output_schema=payload.output_schema,
        safety_level=payload.safety_level,
        timeout_seconds=payload.timeout_seconds,
        metadata=payload.metadata,
    )
    return ok(ToolDefinitionResponse.model_validate(tool))


@router.get("/projects/{project_id}/tools")
async def list_tool_definitions(
    project_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    tools = await service.list_tools(project_id)
    return ok([ToolDefinitionResponse.model_validate(t) for t in tools])


@router.get("/projects/{project_id}/tools/{tool_id}")
async def get_tool_definition(
    project_id: UUID,
    tool_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    tool = await service.get_tool(tool_id)
    if tool.project_id != project_id:
        raise NotFoundError("Tool definition not found in project.")
    return ok(ToolDefinitionResponse.model_validate(tool))


# ------------------------------------------------------------- Agent Endpoints
@router.post("/projects/{project_id}/agents", status_code=http_status.HTTP_201_CREATED)
async def create_agent_definition(
    project_id: UUID,
    payload: AgentDefinitionCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = AgentService(session)
    agent = await service.create_agent(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        agent_type=payload.agent_type,
        provider_id=payload.provider_id,
        model_id=payload.model_id,
        environment_id=payload.environment_id,
        system_prompt=payload.system_prompt,
        tool_manifest=payload.tool_manifest,
        retrieval_configuration=payload.retrieval_configuration,
        configuration=payload.configuration,
        metadata=payload.metadata,
        created_by=user.id,
    )
    return ok(AgentDefinitionResponse.model_validate(agent))


@router.get("/projects/{project_id}/agents")
async def list_agent_definitions(
    project_id: UUID,
    is_active: bool | None = Query(default=None),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    agents = await service.list_agents(project_id, is_active=is_active)
    return ok([AgentDefinitionResponse.model_validate(a) for a in agents])


@router.get("/projects/{project_id}/agents/{agent_id}")
async def get_agent_definition(
    project_id: UUID,
    agent_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    agent = await service.get_agent(agent_id)
    if agent.project_id != project_id:
        raise NotFoundError("Agent definition not found in project.")
    return ok(AgentDefinitionResponse.model_validate(agent))


@router.put("/projects/{project_id}/agents/{agent_id}")
async def update_agent_definition(
    project_id: UUID,
    agent_id: UUID,
    payload: AgentDefinitionUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = AgentService(session)
    agent = await service.get_agent(agent_id)
    if agent.project_id != project_id:
        raise NotFoundError("Agent definition not found in project.")

    updates = payload.model_dump(exclude_unset=True)
    updated = await service.update_agent(agent_id, updates)
    return ok(AgentDefinitionResponse.model_validate(updated))


# ------------------------------------------------------------- Agent Runs Endpoints
@router.post("/projects/{project_id}/agents/{agent_id}/runs", status_code=http_status.HTTP_201_CREATED)
async def start_agent_run(
    project_id: UUID,
    agent_id: UUID,
    payload: AgentRunCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = AgentService(session)
    agent = await service.get_agent(agent_id)
    if agent.project_id != project_id:
        raise NotFoundError("Agent definition not found in project.")

    task_dict = payload.task.model_dump() if payload.task else None

    run = await service.start_run(
        project_id=project_id,
        agent_id=agent_id,
        environment_id=payload.environment_id,
        dataset_version_id=payload.dataset_version_id,
        test_case_id=payload.test_case_id,
        custom_task=task_dict,
        metadata=payload.metadata,
        created_by=user.id,
    )
    return ok(AgentRunResponse.model_validate(run))


@router.get("/projects/{project_id}/agent-runs")
async def list_agent_runs(
    project_id: UUID,
    agent_id: UUID | None = Query(default=None),
    environment_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    runs = await service.list_runs(
        project_id=project_id,
        agent_id=agent_id,
        environment_id=environment_id,
        status=status,
    )
    return ok([AgentRunResponse.model_validate(r) for r in runs])


@router.get("/projects/{project_id}/agent-runs/{run_id}")
async def get_agent_run(
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise NotFoundError("Agent run not found in project.")
    return ok(AgentRunResponse.model_validate(run))


@router.get("/projects/{project_id}/agent-runs/{run_id}/trajectory")
async def get_agent_run_trajectory(
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise NotFoundError("Agent run not found in project.")
    return ok([AgentTrajectoryStepResponse.model_validate(s) for s in run.trajectory_steps])


@router.post("/projects/{project_id}/agent-runs/{run_id}/evaluate")
async def evaluate_agent_run_endpoint(
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=True)
    service = AgentService(session)
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise NotFoundError("Agent run not found in project.")

    result = await service.evaluate_run(run_id)
    return ok(result)


@router.get("/projects/{project_id}/agent-runs/{run_id}/reliability")
async def get_agent_run_reliability(
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Any:
    await _verify_project_access(project_id, organization_id, user.id, session, require_write=False)
    service = AgentService(session)
    run = await service.get_run(run_id)
    if run.project_id != project_id:
        raise NotFoundError("Agent run not found in project.")

    return ok({
        "agent_id": run.agent_id,
        "agent_version": run.agent_version,
        "reliability_score": run.reliability_score,
        "goal_completion_status": run.goal_completion_status,
        "safety_violations": run.safety_violations,
        "loops_detected": run.loops_detected,
        "reliability_breakdown": run.reliability_breakdown,
        "evaluation_checks": run.evaluation_checks,
    })
