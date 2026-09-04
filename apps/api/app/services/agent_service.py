"""Agent Service orchestrating execution, trajectory recording, and reliability evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailure
from app.models.agent import AgentDefinition, AgentRun, ToolDefinition
from app.repositories.agent import AgentRepository
from app.services.agent_gateway import DeterministicLocalTestAgent, compute_agent_fingerprint
from app.services.agent_reliability import AgentReliabilityScorer
from app.services.trajectory_evaluator import TrajectoryEvaluator


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AgentRepository(session)
        self._evaluator = TrajectoryEvaluator()
        self._scorer = AgentReliabilityScorer()

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
        return await self._repo.create_tool(
            project_id=project_id,
            name=name,
            input_schema=input_schema,
            description=description,
            output_schema=output_schema,
            safety_level=safety_level,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )

    async def list_tools(self, project_id: UUID) -> list[ToolDefinition]:
        return await self._repo.list_tools_by_project(project_id)

    async def get_tool(self, tool_id: UUID) -> ToolDefinition:
        tool = await self._repo.get_tool_by_id(tool_id)
        if not tool:
            raise NotFoundError("Tool definition not found.")
        return tool

    # ------------------------------------------------------------- Agents
    async def create_agent(
        self,
        *,
        project_id: UUID,
        name: str,
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
        fingerprint = compute_agent_fingerprint(
            agent_name=name,
            agent_type=agent_type,
            version=1,
            system_prompt=system_prompt,
            tool_manifest=tool_manifest,
            configuration=configuration,
            model_id=model_id,
            provider_id=provider_id,
        )
        return await self._repo.create_agent(
            project_id=project_id,
            name=name,
            configuration_fingerprint=fingerprint,
            description=description,
            agent_type=agent_type,
            provider_id=provider_id,
            model_id=model_id,
            environment_id=environment_id,
            system_prompt=system_prompt,
            tool_manifest=tool_manifest,
            retrieval_configuration=retrieval_configuration,
            configuration=configuration,
            metadata=metadata,
            created_by=created_by,
        )

    async def get_agent(self, agent_id: UUID) -> AgentDefinition:
        agent = await self._repo.get_agent_by_id(agent_id)
        if not agent:
            raise NotFoundError("Agent definition not found.")
        return agent

    async def list_agents(self, project_id: UUID, is_active: bool | None = None) -> list[AgentDefinition]:
        return await self._repo.list_agents_by_project(project_id, is_active=is_active)

    async def update_agent(
        self, agent_id: UUID, updates: dict[str, Any]
    ) -> AgentDefinition:
        agent = await self.get_agent(agent_id)
        new_version = agent.version + 1
        new_fingerprint = compute_agent_fingerprint(
            agent_name=updates.get("name") or agent.name,
            agent_type=updates.get("agent_type") or agent.agent_type,
            version=new_version,
            system_prompt=updates.get("system_prompt") if "system_prompt" in updates else agent.system_prompt,
            tool_manifest=updates.get("tool_manifest") if "tool_manifest" in updates else agent.tool_manifest,
            configuration=updates.get("configuration") if "configuration" in updates else agent.configuration,
            model_id=updates.get("model_id") if "model_id" in updates else agent.model_id,
            provider_id=updates.get("provider_id") if "provider_id" in updates else agent.provider_id,
        )
        return await self._repo.update_agent(agent, new_fingerprint=new_fingerprint, **updates)

    # ------------------------------------------------------------- Agent Runs
    async def start_run(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        environment_id: UUID | None = None,
        dataset_version_id: UUID | None = None,
        test_case_id: UUID | None = None,
        custom_task: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: UUID | None = None,
    ) -> AgentRun:
        agent = await self.get_agent(agent_id)
        trace_id = f"agent_trace_{uuid4().hex[:12]}"

        task_payload = custom_task or {
            "task_id": f"task_{uuid4().hex[:8]}",
            "instruction": f"Run task for agent {agent.name}",
            "expected_tools": [t if isinstance(t, str) else t.get("name") for t in (agent.tool_manifest or []) if t],
            "max_steps": (agent.configuration or {}).get("max_steps", 15),
            "max_tool_calls": (agent.configuration or {}).get("max_tool_calls", 25),
        }
        merged_meta = dict(metadata or {})
        merged_meta["task"] = task_payload

        run = await self._repo.create_run(
            project_id=project_id,
            agent_id=agent_id,
            agent_version=agent.version,
            agent_fingerprint=agent.configuration_fingerprint,
            dataset_version_id=dataset_version_id,
            test_case_id=test_case_id,
            environment_id=environment_id or agent.environment_id,
            trace_id=trace_id,
            status="RUNNING",
            metadata=merged_meta,
            created_by=created_by,
        )

        # Execute using Local Test Agent
        raw_steps = DeterministicLocalTestAgent.execute(agent_def=agent, task=task_payload)

        # Ingest steps with sensitive data protection
        from app.core.sensitive_data import sanitize_payload
        for step in raw_steps:
            tool_args, _, _ = sanitize_payload(step.get("tool_arguments"))
            tool_res, _, _ = sanitize_payload(step.get("tool_result"))
            model_inp, _, _ = sanitize_payload(step.get("model_input"))
            model_out, _, _ = sanitize_payload(step.get("model_output"))
            err_msg, _, _ = sanitize_payload(step.get("error_message"))

            await self._repo.add_trajectory_step(
                agent_run_id=run.id,
                step_number=step["step_number"],
                step_type=step["step_type"],
                status=step.get("status", "SUCCESS"),
                tool_name=step.get("tool_name"),
                tool_call_id=step.get("tool_call_id"),
                tool_arguments=tool_args,
                tool_result=tool_res,
                model_input=model_inp,
                model_output=model_out,
                error_category=step.get("error_category"),
                error_message=err_msg,
                duration_ms=step.get("duration_ms"),
                timestamp=step.get("timestamp"),
            )

        # Evaluate the completed trajectory immediately
        await self.evaluate_run(run.id, task=task_payload)
        return (await self._repo.get_run_by_id(run.id)) or run

    async def get_run(self, run_id: UUID) -> AgentRun:
        run = await self._repo.get_run_by_id(run_id)
        if not run:
            raise NotFoundError("Agent run not found.")
        return run

    async def list_runs(
        self,
        project_id: UUID,
        agent_id: UUID | None = None,
        environment_id: UUID | None = None,
        status: str | None = None,
    ) -> list[AgentRun]:
        return await self._repo.list_runs_by_project(
            project_id=project_id,
            agent_id=agent_id,
            environment_id=environment_id,
            status=status,
        )

    # ------------------------------------------------------------- Trajectory & Evaluation
    async def evaluate_run(
        self, run_id: UUID, task: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        run = await self.get_run(run_id)
        steps_objs = await self._repo.get_trajectory_steps(run_id)
        steps = [
            {
                "step_number": s.step_number,
                "step_type": s.step_type,
                "status": s.status,
                "tool_name": s.tool_name,
                "tool_arguments": s.tool_arguments,
                "tool_result": s.tool_result,
                "error_category": s.error_category,
                "error_message": s.error_message,
                "duration_ms": s.duration_ms,
            }
            for s in steps_objs
        ]

        # Fetch registered tools for schema checking
        tools = await self._repo.list_tools_by_project(run.project_id)
        tools_map = {t.name: t for t in tools}

        task_payload = task or (run.metadata_ or {}).get("task") or {
            "max_steps": 15,
            "max_tool_calls": 25,
            "expected_tools": [],
            "forbidden_tools": [],
        }

        # Run trajectory evaluation
        eval_res = self._evaluator.evaluate(
            steps=steps, task=task_payload, tools_map=tools_map
        )
        metrics = eval_res["metrics"]
        goal_status = eval_res["goal_completion_status"]

        # Compute reliability score
        score, breakdown, safety_status = self._scorer.compute_score(
            goal_status=goal_status,
            evaluation_results=eval_res,
            max_steps=task_payload.get("max_steps", 15),
            max_tool_calls=task_payload.get("max_tool_calls", 25),
        )

        final_run_status = (
            "COMPLETED" if eval_res["overall_status"] in ("PASS", "WARNING")
            else "FAILED"
        )
        total_duration = sum(s.get("duration_ms") or 0.0 for s in steps)

        # Update run record with evaluated metrics
        await self._repo.update_run(
            run,
            status=final_run_status,
            goal_completion_status=goal_status,
            total_steps=metrics["total_steps"],
            total_tool_calls=metrics["total_tool_calls"],
            successful_tool_calls=metrics["successful_tool_calls"],
            failed_tool_calls=metrics["failed_tool_calls"],
            recovered_failures=metrics["recovered_failures"],
            unrecovered_failures=metrics["unrecovered_failures"],
            loops_detected=metrics["loops_detected"],
            safety_violations=metrics["safety_violations"],
            duration_ms=total_duration,
            reliability_score=score,
            reliability_breakdown=breakdown,
            evaluation_checks=eval_res["checks"],
            completed_at=datetime.now(UTC),
        )

        return {
            "run_id": run.id,
            "overall_status": eval_res["overall_status"],
            "checks": eval_res["checks"],
            "reliability_score": score,
            "loops_detected": metrics["loops_detected"],
            "safety_violations": metrics["safety_violations"],
            "recovery_rate": metrics["recovery_rate"],
            "recommendations": [
                {
                    "type": "SAFETY_ACTION",
                    "fact": f"{metrics['safety_violations']} safety violation(s) recorded.",
                    "suggestion": "Revoke forbidden tools and apply strictly bounded parameters.",
                }
            ]
            if metrics["safety_violations"] > 0
            else [],
        }
