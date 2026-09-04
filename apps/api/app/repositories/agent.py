"""Repository for Phase 11 Agent definitions, tools, runs, and trajectories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import (
    AgentDefinition,
    AgentRun,
    AgentTrajectoryStep,
    ToolDefinition,
)


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- Tools
    async def create_tool(
        self,
        *,
        project_id: UUID,
        name: str,
        input_schema: dict[str, Any],
        description: str | None = None,
        output_schema: dict[str, Any] | None = None,
        safety_level: str = "LOW",
        timeout_seconds: int = 30,
        metadata: dict[str, Any] | None = None,
    ) -> ToolDefinition:
        tool = ToolDefinition(
            project_id=project_id,
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            version=1,
            safety_level=safety_level,
            timeout_seconds=timeout_seconds,
            metadata_=metadata,
        )
        self._session.add(tool)
        await self._session.flush()
        return tool

    async def get_tool_by_id(self, tool_id: UUID) -> ToolDefinition | None:
        stmt = select(ToolDefinition).where(ToolDefinition.id == tool_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_tool_by_name(
        self, project_id: UUID, name: str, version: int | None = None
    ) -> ToolDefinition | None:
        conditions = [ToolDefinition.project_id == project_id, ToolDefinition.name == name]
        if version is not None:
            conditions.append(ToolDefinition.version == version)
        stmt = select(ToolDefinition).where(and_(*conditions)).order_by(desc(ToolDefinition.version))
        res = await self._session.execute(stmt)
        return res.scalars().first()

    async def list_tools_by_project(self, project_id: UUID) -> list[ToolDefinition]:
        stmt = (
            select(ToolDefinition)
            .where(ToolDefinition.project_id == project_id)
            .order_by(desc(ToolDefinition.created_at))
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    # ------------------------------------------------------------- Agent Definitions
    async def create_agent(
        self,
        *,
        project_id: UUID,
        name: str,
        configuration_fingerprint: str,
        description: str | None = None,
        agent_type: str = "TOOL_AGENT",
        provider_id: UUID | None = None,
        model_id: UUID | None = None,
        environment_id: UUID | None = None,
        system_prompt: str | None = None,
        tool_manifest: list[Any] | None = None,
        retrieval_configuration: dict[str, Any] | None = None,
        configuration: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: UUID | None = None,
    ) -> AgentDefinition:
        agent = AgentDefinition(
            project_id=project_id,
            name=name,
            description=description,
            agent_type=agent_type,
            version=1,
            provider_id=provider_id,
            model_id=model_id,
            environment_id=environment_id,
            system_prompt=system_prompt,
            tool_manifest=tool_manifest,
            retrieval_configuration=retrieval_configuration,
            configuration=configuration,
            metadata_=metadata,
            configuration_fingerprint=configuration_fingerprint,
            is_active=True,
            created_by=created_by,
        )
        self._session.add(agent)
        await self._session.flush()
        return agent

    async def get_agent_by_id(self, agent_id: UUID) -> AgentDefinition | None:
        stmt = (
            select(AgentDefinition)
            .where(AgentDefinition.id == agent_id)
            .options(selectinload(AgentDefinition.runs))
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_agents_by_project(
        self, project_id: UUID, is_active: bool | None = None
    ) -> list[AgentDefinition]:
        conditions = [AgentDefinition.project_id == project_id]
        if is_active is not None:
            conditions.append(AgentDefinition.is_active == is_active)
        stmt = (
            select(AgentDefinition)
            .where(and_(*conditions))
            .order_by(desc(AgentDefinition.created_at))
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def update_agent(
        self,
        agent: AgentDefinition,
        new_fingerprint: str,
        **updates: Any,
    ) -> AgentDefinition:
        for k, v in updates.items():
            if hasattr(agent, k) and v is not None:
                setattr(agent, k, v)
        agent.version += 1
        agent.configuration_fingerprint = new_fingerprint
        agent.updated_at = datetime.now(UTC)
        await self._session.flush()
        return agent

    # ------------------------------------------------------------- Agent Runs
    async def create_run(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        agent_version: int,
        agent_fingerprint: str,
        dataset_version_id: UUID | None = None,
        test_case_id: UUID | None = None,
        environment_id: UUID | None = None,
        trace_id: str | None = None,
        status: str = "PENDING",
        metadata: dict[str, Any] | None = None,
        created_by: UUID | None = None,
    ) -> AgentRun:
        run = AgentRun(
            project_id=project_id,
            agent_id=agent_id,
            agent_version=agent_version,
            agent_fingerprint=agent_fingerprint,
            dataset_version_id=dataset_version_id,
            test_case_id=test_case_id,
            environment_id=environment_id,
            trace_id=trace_id,
            status=status,
            goal_completion_status="UNKNOWN",
            metadata_=metadata,
            created_by=created_by,
        )
        self._session.add(run)
        await self._session.flush()
        loaded = await self.get_run_by_id(run.id)
        return loaded or run

    async def get_run_by_id(self, run_id: UUID) -> AgentRun | None:
        stmt = (
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .options(selectinload(AgentRun.trajectory_steps))
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_runs_by_project(
        self,
        project_id: UUID,
        agent_id: UUID | None = None,
        environment_id: UUID | None = None,
        status: str | None = None,
    ) -> list[AgentRun]:
        conditions = [AgentRun.project_id == project_id]
        if agent_id is not None:
            conditions.append(AgentRun.agent_id == agent_id)
        if environment_id is not None:
            conditions.append(AgentRun.environment_id == environment_id)
        if status is not None:
            conditions.append(AgentRun.status == status)
        stmt = select(AgentRun).where(and_(*conditions)).order_by(desc(AgentRun.created_at))
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def update_run(self, run: AgentRun, **updates: Any) -> AgentRun:
        for k, v in updates.items():
            if hasattr(run, k) and v is not None:
                setattr(run, k, v)
        await self._session.flush()
        return run

    # ------------------------------------------------------------- Trajectory Steps
    async def add_trajectory_step(
        self,
        *,
        agent_run_id: UUID,
        step_number: int,
        step_type: str,
        status: str = "SUCCESS",
        parent_step_id: UUID | None = None,
        span_id: str | None = None,
        tool_definition_id: UUID | None = None,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        tool_arguments: dict[str, Any] | None = None,
        tool_result: dict[str, Any] | None = None,
        model_input: str | None = None,
        model_output: str | None = None,
        error_category: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTrajectoryStep:
        step = AgentTrajectoryStep(
            agent_run_id=agent_run_id,
            step_number=step_number,
            step_type=step_type,
            status=status,
            parent_step_id=parent_step_id,
            span_id=span_id,
            tool_definition_id=tool_definition_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_arguments=tool_arguments,
            tool_result=tool_result,
            model_input=model_input,
            model_output=model_output,
            error_category=error_category,
            error_message=error_message,
            duration_ms=duration_ms,
            timestamp=timestamp or datetime.now(UTC),
            metadata_=metadata,
        )
        self._session.add(step)
        await self._session.flush()
        return step

    async def get_trajectory_steps(self, run_id: UUID) -> list[AgentTrajectoryStep]:
        stmt = (
            select(AgentTrajectoryStep)
            .where(AgentTrajectoryStep.agent_run_id == run_id)
            .order_by(AgentTrajectoryStep.step_number)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())
