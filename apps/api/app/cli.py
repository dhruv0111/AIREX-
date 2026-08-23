"""AIREX CLI foundation (spec §67).

Commands (Phase 0):
    airex version
    airex health
    airex login
    airex project list

Run:  python -m app.cli <command>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from app import __version__

CONFIG_PATH = Path.home() / ".airex" / "config.json"


def _api_url() -> str:
    return os.environ.get("NEXT_PUBLIC_API_URL", os.environ.get("API_URL", "http://localhost:8000"))


def cmd_version(_args: argparse.Namespace) -> int:
    print(json.dumps({"name": "airex", "version": __version__}))
    return 0


def cmd_health(_args: argparse.Namespace) -> int:
    try:
        resp = httpx.get(f"{_api_url()}/health", timeout=10)
        body = resp.json()
        print(json.dumps(body))
        return 0 if resp.status_code == 200 else 1
    except Exception as exc:  # pragma: no cover
        print(f"error: cannot reach API at {_api_url()}: {exc}", file=sys.stderr)
        return 1


def cmd_login(args: argparse.Namespace) -> int:
    email = args.email or input("Email: ")
    password = args.password or input("Password: ")
    try:
        resp = httpx.post(
            f"{_api_url()}/api/v1/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        if resp.status_code != 200:
            print(f"error: login failed ({resp.status_code}): {resp.text}", file=sys.stderr)
            return 1
        data = resp.json()["data"]
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(
                {"access_token": data["access_token"], "refresh_token": data["refresh_token"]}
            )
        )
        print(json.dumps({"status": "ok", "user": email}))
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"error: {exc}", file=sys.stderr)
        return 1


def cmd_project_list(args: argparse.Namespace) -> int:
    if not CONFIG_PATH.exists():
        print("error: not logged in. Run: airex login", file=sys.stderr)
        return 1
    token = json.loads(CONFIG_PATH.read_text())["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    if args.organization:
        headers["X-Organization-Id"] = args.organization
    try:
        resp = httpx.get(f"{_api_url()}/api/v1/projects", headers=headers, timeout=15)
        if resp.status_code == 401:
            print("error: session expired. Run: airex login", file=sys.stderr)
            return 1
        if resp.status_code != 200:
            print(f"error: {resp.status_code} {resp.text}", file=sys.stderr)
            return 1
        body = resp.json()
        for project in body.get("data", []):
            print(f"{project['id']}\t{project['name']}\t{project['status']}")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="airex", description="AIREX CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print version")
    sub.add_parser("health", help="check API health")
    login = sub.add_parser("login", help="authenticate")
    login.add_argument("--email", default=None)
    login.add_argument("--password", default=None)
    projects = sub.add_parser("project", help="project commands")
    projects.add_argument("--organization", default=None)
    project_sub = projects.add_subparsers(dest="project_command", required=True)
    project_sub.add_parser("list", help="list projects")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        return cmd_version(args)
    if args.command == "health":
        return cmd_health(args)
    if args.command == "login":
        return cmd_login(args)
    if args.command == "project" and args.project_command == "list":
        return cmd_project_list(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
