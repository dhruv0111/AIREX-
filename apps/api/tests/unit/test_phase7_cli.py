"""Unit tests for AIREX CLI parsing and validation (Phase 7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest
import yaml

from app.cli import build_parser, validate_config, main


def test_cli_parser_builds() -> None:
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_cli_parser_version() -> None:
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.command == "version"


def test_cli_parser_init() -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--project", "foo", "--dataset", "bar"])
    assert args.command == "init"
    assert args.project == "foo"
    assert args.dataset == "bar"


def test_cli_parser_auth_login() -> None:
    parser = build_parser()
    args = parser.parse_args(["auth", "login", "--email", "test@test.com", "--password", "secret"])
    assert args.command == "auth"
    assert args.auth_command == "login"
    assert args.email == "test@test.com"
    assert args.password == "secret"


def test_cli_parser_experiments_run() -> None:
    parser = build_parser()
    args = parser.parse_args(["experiments", "run", "--config", "airex.yaml", "--poll-interval", "5.0"])
    assert args.command == "experiments"
    assert args.experiments_command == "run"
    assert args.config == "airex.yaml"
    assert args.poll_interval == 5.0


def test_validate_config_success() -> None:
    valid_cfg = {
        "version": "1",
        "project": "my-project",
        "experiment": {
            "dataset": "production-dataset",
            "baseline": {"model": "gpt-4o"},
            "candidate": {"model": "claude-3-5"},
        },
        "quality_gates": [
            {"metric": "accuracy", "operator": "gte", "threshold": 0.85, "required": True}
        ],
    }
    # Should not raise any exceptions
    validate_config(valid_cfg)


@pytest.mark.parametrize(
    "invalid_cfg",
    [
        {},
        {"version": "2"},
        {"version": "1", "project": ""},
        {"version": "1", "project": "foo", "experiment": {}},
        {"version": "1", "project": "foo", "experiment": {"dataset": ""}},
        {
            "version": "1",
            "project": "foo",
            "experiment": {
                "dataset": "bar",
                "baseline": {},
                "candidate": {"model": "claude"},
            },
        },
        {
            "version": "1",
            "project": "foo",
            "experiment": {
                "dataset": "bar",
                "baseline": {"model": "gpt"},
                "candidate": {},
            },
        },
        {
            "version": "1",
            "project": "foo",
            "experiment": {
                "dataset": "bar",
                "baseline": {"model": "gpt"},
                "candidate": {"model": "claude"},
            },
            "quality_gates": [{"metric": "acc", "operator": "invalid", "threshold": 0.5}],
        },
        {
            "version": "1",
            "project": "foo",
            "experiment": {
                "dataset": "bar",
                "baseline": {"model": "gpt"},
                "candidate": {"model": "claude"},
            },
            "quality_gates": [{"metric": "acc", "operator": "gte", "threshold": "non-numeric"}],
        },
    ],
)
def test_validate_config_failures(invalid_cfg: dict) -> None:
    with pytest.raises(SystemExit) as exc:
        validate_config(invalid_cfg)
    assert exc.value.code == 2
