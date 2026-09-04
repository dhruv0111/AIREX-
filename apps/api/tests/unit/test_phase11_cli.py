"""Unit tests for Phase 11 CLI commands."""

import argparse
import pytest
from unittest.mock import patch, MagicMock

from app.cli import (
    build_parser,
    cmd_agents_create,
    cmd_agents_list,
    cmd_agents_run,
    cmd_agents_status,
    cmd_agents_trajectory,
    cmd_agents_evaluate,
    cmd_agents_benchmark,
)


def test_cli_agents_parser_registration():
    """Verify all Phase 11 agents commands and options are registered in parser."""
    parser = build_parser()
    
    # create
    args = parser.parse_args(["agents", "create", "--name", "AgentX", "--agent-type", "TOOL_AGENT", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.command == "agents"
    assert args.agents_command == "create"
    assert args.name == "AgentX"

    # list
    args = parser.parse_args(["agents", "list", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.agents_command == "list"

    # run
    args = parser.parse_args(["agents", "run", "--agent-id", "00000000-0000-0000-0000-000000000002", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.agents_command == "run"
    assert args.agent_id == "00000000-0000-0000-0000-000000000002"

    # status
    args = parser.parse_args(["agents", "status", "--run-id", "00000000-0000-0000-0000-000000000003", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.agents_command == "status"

    # trajectory
    args = parser.parse_args(["agents", "trajectory", "--run-id", "00000000-0000-0000-0000-000000000003", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.agents_command == "trajectory"

    # evaluate
    args = parser.parse_args(["agents", "evaluate", "--run-id", "00000000-0000-0000-0000-000000000003", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.agents_command == "evaluate"

    # benchmark
    args = parser.parse_args(["agents", "benchmark", "--agent-id", "00000000-0000-0000-0000-000000000002", "--project-id", "00000000-0000-0000-0000-000000000001"])
    assert args.agents_command == "benchmark"


@patch("app.cli._request")
def test_cmd_agents_create_success(mock_req):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"data": {"id": "ag-123", "name": "Agent1", "version": 1}}
    mock_req.return_value = mock_resp

    args = argparse.Namespace(
        name="Agent1",
        description="Desc",
        agent_type="TOOL_AGENT",
        prompt="Prompt",
        project_id="00000000-0000-0000-0000-000000000001",
        output="table",
    )
    exit_code = cmd_agents_create(args)
    assert exit_code == 0


@patch("app.cli._request")
def test_cmd_agents_evaluate_success(mock_req):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "overall_status": "PASS",
            "reliability_score": 92.5,
            "loops_detected": 0,
            "safety_violations": 0,
            "checks": [{"check_name": "goal_completion", "status": "PASS", "explanation": "Success"}],
        }
    }
    mock_req.return_value = mock_resp

    args = argparse.Namespace(
        run_id="00000000-0000-0000-0000-000000000003",
        project_id="00000000-0000-0000-0000-000000000001",
        output="table",
    )
    exit_code = cmd_agents_evaluate(args)
    assert exit_code == 0
