"""Phase 11 AI Agent Evaluation & Trajectory Testing Integration Tests."""

from __future__ import annotations

import pytest
from uuid import UUID

from tests.integration._helpers import (
    create_project,
    headers_for,
    org_id,
    register,
)
from app.workers.tasks import TASK_REGISTRY

EMAIL = "p11_agent_int@example.com"


async def _setup_p11(client, email: str = EMAIL):
    await register(client, email)
    headers = await headers_for(client, email)
    org = await org_id(client, headers)
    project = await create_project(
        client, headers, org, name="P11 Agent Project", slug=f"p11-{email.split('@')[0]}"
    )

    # Create environment
    env_resp = await client.post(
        f"/api/v1/projects/{project}/environments",
        json={"name": "Staging", "environment_type": "STAGING"},
        headers={**headers, "X-Organization-Id": org},
    )
    assert env_resp.status_code == 201, env_resp.text
    env_id = env_resp.json()["data"]["id"]

    return headers, org, project, env_id


@pytest.mark.asyncio
async def test_tool_definition_crud(client):
    """Test creating, listing, and retrieving tool definitions."""
    headers, org, project, env_id = await _setup_p11(client, email="p11_tools@example.com")
    auth_headers = {**headers, "X-Organization-Id": org}

    # 1. Create tool
    payload = {
        "name": "calculator",
        "description": "Performs basic arithmetic operations",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        "safety_level": "LOW",
        "timeout_seconds": 15,
    }
    resp = await client.post(f"/api/v1/projects/{project}/tools", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    tool_data = resp.json()["data"]
    assert tool_data["name"] == "calculator"
    assert tool_data["safety_level"] == "LOW"
    tool_id = tool_data["id"]

    # 2. List tools
    list_resp = await client.get(f"/api/v1/projects/{project}/tools", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(t["id"] == tool_id for t in list_resp.json()["data"])

    # 3. Get single tool
    get_resp = await client.get(f"/api/v1/projects/{project}/tools/{tool_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "calculator"


@pytest.mark.asyncio
async def test_agent_definition_lifecycle(client):
    """Test creating, listing, and updating an agent definition."""
    headers, org, project, env_id = await _setup_p11(client, email="p11_agents@example.com")
    auth_headers = {**headers, "X-Organization-Id": org}

    # 1. Create Agent
    create_payload = {
        "name": "Research Agent",
        "description": "Analyzes market research",
        "agent_type": "TOOL_AGENT",
        "system_prompt": "You are a market researcher.",
        "tool_manifest": [{"name": "calculator"}],
        "configuration": {"max_steps": 10},
    }
    resp = await client.post(f"/api/v1/projects/{project}/agents", json=create_payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    agent = resp.json()["data"]
    assert agent["name"] == "Research Agent"
    assert agent["version"] == 1
    assert len(agent["configuration_fingerprint"]) == 64
    agent_id = agent["id"]
    fp_v1 = agent["configuration_fingerprint"]

    # 2. Update Agent (Bump version & fingerprint)
    update_payload = {
        "system_prompt": "You are an advanced researcher with financial domain knowledge.",
    }
    up_resp = await client.put(f"/api/v1/projects/{project}/agents/{agent_id}", json=update_payload, headers=auth_headers)
    assert up_resp.status_code == 200, up_resp.text
    updated = up_resp.json()["data"]
    assert updated["version"] == 2
    assert updated["configuration_fingerprint"] != fp_v1


@pytest.mark.asyncio
async def test_agent_run_execution_and_trajectory(client):
    """Test executing an agent task, recording trajectory steps, and computing reliability score."""
    headers, org, project, env_id = await _setup_p11(client, email="p11_run@example.com")
    auth_headers = {**headers, "X-Organization-Id": org}

    # Create agent
    create_resp = await client.post(
        f"/api/v1/projects/{project}/agents",
        json={
            "name": "Math Assistant",
            "agent_type": "TOOL_AGENT",
            "tool_manifest": ["calculator"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["data"]["id"]

    # Start run with custom task
    run_payload = {
        "environment_id": env_id,
        "task": {
            "task_id": "math_task_1",
            "instruction": "Compute 24 * 7",
            "expected_tools": ["calculator"],
            "forbidden_tools": ["delete_data"],
            "max_steps": 10,
            "max_tool_calls": 5,
        },
    }
    run_resp = await client.post(f"/api/v1/projects/{project}/agents/{agent_id}/runs", json=run_payload, headers=auth_headers)
    assert run_resp.status_code == 201, run_resp.text
    run_data = run_resp.json()["data"]
    assert run_data["status"] == "COMPLETED"
    assert run_data["goal_completion_status"] == "COMPLETED"
    assert run_data["reliability_score"] is not None
    assert run_data["reliability_score"] >= 80.0
    run_id = run_data["id"]

    # Retrieve trajectory steps
    traj_resp = await client.get(f"/api/v1/projects/{project}/agent-runs/{run_id}/trajectory", headers=auth_headers)
    assert traj_resp.status_code == 200
    steps = traj_resp.json()["data"]
    assert len(steps) >= 3
    step_types = [s["step_type"] for s in steps]
    assert "MODEL_REQUEST" in step_types
    assert "TOOL_CALL" in step_types
    assert "FINAL" in step_types

    # Retrieve reliability breakdown
    rel_resp = await client.get(f"/api/v1/projects/{project}/agent-runs/{run_id}/reliability", headers=auth_headers)
    assert rel_resp.status_code == 200
    rel_data = rel_resp.json()["data"]
    assert rel_data["reliability_score"] == run_data["reliability_score"]
    assert rel_data["safety_violations"] == 0


@pytest.mark.asyncio
async def test_agent_run_simulated_loop_detection(client):
    """Test running an agent that enters a repetitive tool loop triggers loop detection."""
    headers, org, project, env_id = await _setup_p11(client, email="p11_loop@example.com")
    auth_headers = {**headers, "X-Organization-Id": org}

    create_resp = await client.post(
        f"/api/v1/projects/{project}/agents",
        json={"name": "Loopy Agent", "agent_type": "TOOL_AGENT"},
        headers=auth_headers,
    )
    agent_id = create_resp.json()["data"]["id"]

    run_payload = {
        "task": {
            "task_id": "loop_test",
            "instruction": "Search for news repeatedly",
            "metadata": {"simulate_loop": True},
        },
    }
    run_resp = await client.post(f"/api/v1/projects/{project}/agents/{agent_id}/runs", json=run_payload, headers=auth_headers)
    assert run_resp.status_code == 201, run_resp.text
    run_data = run_resp.json()["data"]
    assert run_data["loops_detected"] >= 1


@pytest.mark.asyncio
async def test_agent_run_forbidden_tool_safety_block(client):
    """Test that invoking a forbidden tool triggers a critical safety violation and blocks deployment."""
    headers, org, project, env_id = await _setup_p11(client, email="p11_safety@example.com")
    auth_headers = {**headers, "X-Organization-Id": org}

    create_resp = await client.post(
        f"/api/v1/projects/{project}/agents",
        json={"name": "Dangerous Agent", "agent_type": "TOOL_AGENT"},
        headers=auth_headers,
    )
    agent_id = create_resp.json()["data"]["id"]

    run_payload = {
        "task": {
            "task_id": "safety_test",
            "instruction": "Attempt unauthorized database deletion",
            "forbidden_tools": ["delete_database"],
            "metadata": {"simulate_forbidden_tool": True},
        },
    }
    run_resp = await client.post(f"/api/v1/projects/{project}/agents/{agent_id}/runs", json=run_payload, headers=auth_headers)
    assert run_resp.status_code == 201, run_resp.text
    run_data = run_resp.json()["data"]
    assert run_data["safety_violations"] >= 1

    # Check evaluation endpoint
    eval_resp = await client.post(f"/api/v1/projects/{project}/agent-runs/{run_data['id']}/evaluate", headers=auth_headers)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()["data"]
    assert eval_data["overall_status"] == "BLOCKED"
    assert eval_data["safety_violations"] >= 1
