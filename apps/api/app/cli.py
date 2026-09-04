"""AIREX CLI (Phase 7 - CI/CD Integration & Developer Quality Gates).

Commands:
    airex version
    airex health
    airex auth [login|logout|status]
    airex projects [list|current]
    airex datasets [list|validate]
    airex experiments [create|run|status|results|cancel]
    airex evaluations [run|results]
    airex quality-gate check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import yaml

from app import __version__

CONFIG_PATH = Path.home() / ".airex" / "config.json"


def _api_url() -> str:
    return os.environ.get("AIREX_API_URL", os.environ.get("NEXT_PUBLIC_API_URL", "http://localhost:8000"))


def _get_token() -> str | None:
    # 1. Check environment variable
    env_token = os.environ.get("AIREX_API_TOKEN")
    if env_token:
        return env_token

    # 2. Check local secure config file
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())["access_token"]
        except Exception:
            pass
    return None


def _get_project_id(args: argparse.Namespace) -> str | None:
    # 1. From arguments
    if getattr(args, "project_id", None):
        return args.project_id

    # 2. From environment variable
    env_proj = os.environ.get("AIREX_PROJECT_ID")
    if env_proj:
        return env_proj

    # 3. Load from local YAML config if present
    yaml_path = Path("airex.yaml")
    if yaml_path.exists():
        try:
            cfg = yaml.safe_load(yaml_path.read_text())
            if cfg and cfg.get("project"):
                return cfg["project"]
        except Exception:
            pass

    return None


def _is_ci() -> bool:
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("GITLAB_CI") == "true"


def _is_non_interactive(args: argparse.Namespace) -> bool:
    return getattr(args, "non_interactive", False) or _is_ci()


def _request(
    method: str,
    path: str,
    *,
    json_data: Any = None,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    token = _get_token()
    req_headers = {}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if headers:
        req_headers.update(headers)

    url = f"{_api_url()}{path}"
    try:
        resp = httpx.request(
            method,
            url,
            json=json_data,
            params=params,
            headers=req_headers,
            timeout=timeout,
        )
        if resp.status_code == 401:
            print("error: authentication failure (401). Please login or configure AIREX_API_TOKEN.", file=sys.stderr)
            sys.exit(3)
        if resp.status_code == 403:
            print("error: access forbidden (403). Check your token scopes.", file=sys.stderr)
            sys.exit(3)
        if resp.status_code == 404:
            print(f"error: resource not found (404) at {path}.", file=sys.stderr)
            sys.exit(4)
        if resp.status_code == 422:
            print(f"error: validation failure (422): {resp.text}", file=sys.stderr)
            sys.exit(2)
        if resp.status_code >= 500:
            print(f"error: API server error ({resp.status_code}): {resp.text}", file=sys.stderr)
            sys.exit(5)
        return resp
    except httpx.RequestError as exc:
        print(f"error: network connection failed: {exc}", file=sys.stderr)
        sys.exit(5)


def _output(args: argparse.Namespace, data: Any, headers_list: list[str] | None = None) -> int:
    mode = getattr(args, "output", "table")
    if mode == "quiet":
        return 0
    if mode == "json":
        print(json.dumps(data, indent=2))
        return 0

    # Table layout mode (default)
    if isinstance(data, list):
        if not data:
            print("No records found.")
            return 0
        
        # Calculate col widths
        keys = headers_list or list(data[0].keys())
        widths = {k: len(k) for k in keys}
        for row in data:
            for k in keys:
                val = str(row.get(k, ""))
                if len(val) > widths[k]:
                    widths[k] = len(val)

        # Print header
        header_row = " | ".join(k.upper().ljust(widths[k]) for k in keys)
        print(header_row)
        print("-" * len(header_row))

        # Print rows
        for row in data:
            print(" | ".join(str(row.get(k, "")).ljust(widths[k]) for k in keys))
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"{k.upper()}: {v}")
    else:
        print(str(data))
    return 0


def load_yaml_config(path: Path) -> dict:
    if not path.exists():
        return {}
    import yaml
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"error: failed to parse YAML config: {e}", file=sys.stderr)
        sys.exit(2)


def validate_config(config: dict) -> None:
    if not config:
        print("error: configuration is empty", file=sys.stderr)
        sys.exit(2)
    if str(config.get("version")) != "1":
        print(f"error: unsupported config version '{config.get('version')}' (expected '1')", file=sys.stderr)
        sys.exit(2)
    if not config.get("project"):
        print("error: config requires 'project' slug/name", file=sys.stderr)
        sys.exit(2)
    
    exp = config.get("experiment")
    if not exp or not isinstance(exp, dict):
        print("error: config requires 'experiment' dictionary", file=sys.stderr)
        sys.exit(2)
    
    if not exp.get("dataset"):
        print("error: config requires 'experiment.dataset'", file=sys.stderr)
        sys.exit(2)
        
    base = exp.get("baseline")
    cand = exp.get("candidate")
    if not base or not isinstance(base, dict) or not base.get("model"):
        print("error: config requires 'experiment.baseline.model'", file=sys.stderr)
        sys.exit(2)
    if not cand or not isinstance(cand, dict) or not cand.get("model"):
        print("error: config requires 'experiment.candidate.model'", file=sys.stderr)
        sys.exit(2)
        
    gates = config.get("quality_gates") or []
    if not isinstance(gates, list):
        print("error: 'quality_gates' must be a list of rules", file=sys.stderr)
        sys.exit(2)
        
    for gate in gates:
        if not isinstance(gate, dict):
            print("error: quality gate rule must be a dictionary", file=sys.stderr)
            sys.exit(2)
        if not gate.get("metric"):
            print("error: quality gate rule requires 'metric'", file=sys.stderr)
            sys.exit(2)
        op = gate.get("operator")
        if not op or op.lower() not in ("gt", "gte", "lt", "lte", "eq"):
            print(f"error: invalid quality gate operator '{op}' (expected gt, gte, lt, lte, eq)", file=sys.stderr)
            sys.exit(2)
        if gate.get("threshold") is None:
            print("error: quality gate rule requires 'threshold'", file=sys.stderr)
            sys.exit(2)
        try:
            float(gate["threshold"])
        except ValueError:
            print("error: quality gate threshold must be a number", file=sys.stderr)
            sys.exit(2)


# ========================================================== Commands Business Logic

def cmd_version(args: argparse.Namespace) -> int:
    return _output(args, {"name": "airex", "version": __version__})


def cmd_health(args: argparse.Namespace) -> int:
    try:
        resp = httpx.get(f"{_api_url()}/health", timeout=10)
        if resp.status_code == 200:
            return _output(args, resp.json())
        print(f"error: health check returned {resp.status_code}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(f"error: health check connection failed: {exc}", file=sys.stderr)
        return 5


def cmd_init(args: argparse.Namespace) -> int:
    yaml_path = Path("airex.yaml")
    if yaml_path.exists() and not _is_non_interactive(args):
        confirm = input("airex.yaml already exists. Overwrite? (y/N): ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return 0

    project = getattr(args, "project", None)
    dataset = getattr(args, "dataset", None)
    baseline_model = getattr(args, "baseline_model", None)
    candidate_model = getattr(args, "candidate_model", None)

    if not _is_non_interactive(args):
        if not project:
            project = input("Project Slug: ").strip()
        if not dataset:
            dataset = input("Dataset Name: ").strip()
        if not baseline_model:
            baseline_model = input("Baseline Model Identifier: ").strip()
        if not candidate_model:
            candidate_model = input("Candidate Model Identifier: ").strip()

    project = project or "my-ai-project"
    dataset = dataset or "production-tests"
    baseline_model = baseline_model or "baseline-model"
    candidate_model = candidate_model or "candidate-model"

    content = {
        "version": "1",
        "project": project,
        "experiment": {
            "dataset": dataset,
            "baseline": {"model": baseline_model},
            "candidate": {"model": candidate_model},
        },
        "quality_gates": [
            {"metric": "exact_match", "operator": "gte", "threshold": 0.90, "required": True},
            {"metric": "latency_ms", "operator": "lte", "threshold": 1000, "required": False},
        ],
    }

    try:
        yaml_path.write_text(yaml.safe_dump(content, sort_keys=False))
        print("Initialized default configuration at airex.yaml")
        return 0
    except Exception as exc:
        print(f"error: failed to write airex.yaml: {exc}", file=sys.stderr)
        return 2


def cmd_login(args: argparse.Namespace) -> int:
    if _is_non_interactive(args) and (not args.email or not args.password):
        print("error: non-interactive login requires --email and --password", file=sys.stderr)
        return 3

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
            return 3
        data = resp.json()["data"]
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(
                {"access_token": data["access_token"], "refresh_token": data["refresh_token"]}
            )
        )
        print("Logged in successfully.")
        return 0
    except Exception as exc:
        print(f"error: login request failed: {exc}", file=sys.stderr)
        return 3


def cmd_logout(args: argparse.Namespace) -> int:
    if CONFIG_PATH.exists():
        try:
            CONFIG_PATH.unlink()
        except Exception:
            pass
    print("Logged out.")
    return 0


def cmd_auth_status(args: argparse.Namespace) -> int:
    token = _get_token()
    if not token:
        print("Not logged in (no active credential token found).", file=sys.stderr)
        return 3
    
    # Check token validity via me endpoint
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(f"{_api_url()}/api/v1/auth/me", headers=headers, timeout=10)
        if resp.status_code == 200:
            body = resp.json()
            email = body["data"]["user"]["email"]
            print(f"Authenticated as {email}.")
            return 0
        else:
            # Try to see if it is a service token by running a basic request
            resp_ci = httpx.get(f"{_api_url()}/api/v1/projects", headers=headers, timeout=10)
            if resp_ci.status_code == 200:
                print("Authenticated via Service Token.")
                return 0

            print("error: session credentials invalid or expired.", file=sys.stderr)
            return 3
    except Exception as exc:
        print(f"error: failed to verify auth status: {exc}", file=sys.stderr)
        return 5


def cmd_project_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/projects")
    projects = resp.json().get("data", [])
    return _output(args, projects, ["id", "name", "slug", "status"])


def cmd_project_current(args: argparse.Namespace) -> int:
    project_id = _get_project_id(args)
    if not project_id:
        print("error: no active project selected.", file=sys.stderr)
        return 4
    return _output(args, {"current_project": project_id})


def cmd_dataset_list(args: argparse.Namespace) -> int:
    project_id = _get_project_id(args)
    if not project_id:
        print("error: project context is required.", file=sys.stderr)
        return 2
    resp = _request("GET", f"/api/v1/projects/{project_id}/datasets")
    datasets = resp.json().get("data", [])
    return _output(args, datasets, ["id", "name", "slug"])


def cmd_dataset_validate(args: argparse.Namespace) -> int:
    yaml_path = Path("airex.yaml")
    if not yaml_path.exists():
        print("error: airex.yaml not found.", file=sys.stderr)
        return 2

    try:
        cfg = yaml.safe_load(yaml_path.read_text())
        validate_config(cfg)
        print("Configuration file is valid.")
        return 0
    except Exception as exc:
        print(f"error: validation failed: {exc}", file=sys.stderr)
        return 2


def cmd_experiment_create(args: argparse.Namespace) -> int:
    yaml_path = Path(args.config)
    if not yaml_path.exists():
        print(f"error: config file '{args.config}' not found.", file=sys.stderr)
        return 2
    
    cfg = load_yaml_config(yaml_path)
    validate_config(cfg)

    project_id = _get_project_id(args)
    if not project_id:
        print("error: project context is required.", file=sys.stderr)
        return 2

    # Map configuration to service endpoints
    # 1. Resolve Dataset
    exp_cfg = cfg.get("experiment") or {}
    dataset_name = exp_cfg.get("dataset")
    
    resp_datasets = _request("GET", f"/api/v1/projects/{project_id}/datasets")
    datasets = resp_datasets.json().get("data", [])
    dataset = next((d for d in datasets if d["name"] == dataset_name or d["slug"] == dataset_name), None)
    if not dataset:
        print(f"error: dataset '{dataset_name}' not found under project.", file=sys.stderr)
        return 4

    # Resolve latest dataset version
    # Since endpoint structure lists dataset versions, fetch versions
    resp_versions = _request("GET", f"/api/v1/datasets/{dataset['id']}/versions")
    versions = resp_versions.json().get("data", [])
    if not versions:
        print(f"error: dataset '{dataset_name}' has no active versions.", file=sys.stderr)
        return 2
    dataset_version_id = versions[0]["id"]

    # 2. Resolve Models
    base_model_name = exp_cfg["baseline"]["model"]
    cand_model_name = exp_cfg["candidate"]["model"]

    resp_models = _request("GET", f"/api/v1/projects/{project_id}/models")
    models = resp_models.json().get("data", [])
    
    base_model = next((m for m in models if m["name"] == base_model_name or m["model_identifier"] == base_model_name), None)
    cand_model = next((m for m in models if m["name"] == cand_model_name or m["model_identifier"] == cand_model_name), None)

    if not base_model:
        print(f"error: baseline model '{base_model_name}' not found.", file=sys.stderr)
        return 4
    if not cand_model:
        print(f"error: candidate model '{cand_model_name}' not found.", file=sys.stderr)
        return 4

    # 3. Map Gates
    gates_payload = []
    for gate in cfg.get("quality_gates", []):
        gates_payload.append({
            "metric_name": gate["metric"],
            "operator": gate["operator"].upper(),
            "threshold": float(gate["threshold"]),
            "severity": "SEVERE" if gate.get("required", True) else "MINOR",
            "is_required": gate.get("required", True),
            "gate_type": "CANDIDATE_VALUE",
        })

    # 4. Create Experiment
    payload = {
        "project_id": project_id,
        "name": f"CLI Experiment - {datetime.now(UTC).strftime('%Y%m%d%H%M')}",
        "description": "Triggered via AIREX CLI",
        "dataset_id": dataset["id"],
        "dataset_version_id": dataset_version_id,
        "baseline": {
            "model_id": base_model["id"],
            "prompt_content": exp_cfg["baseline"].get("prompt_content"),
            "configuration": exp_cfg["baseline"].get("configuration") or {},
        },
        "candidate": {
            "model_id": cand_model["id"],
            "prompt_content": exp_cfg["candidate"].get("prompt_content"),
            "configuration": exp_cfg["candidate"].get("configuration") or {},
        },
        "gates": gates_payload,
    }

    resp = _request("POST", f"/api/v1/projects/{project_id}/experiments", json_data=payload)
    print("Experiment created successfully.")
    return _output(args, resp.json().get("data", {}))


def cmd_experiment_run(args: argparse.Namespace) -> int:
    # Check if a specific --id was supplied
    experiment_id = getattr(args, "id", None)
    if not experiment_id:
        # Load from config and create a new experiment
        yaml_path = Path(args.config)
        if not yaml_path.exists():
            print(f"error: configuration file '{args.config}' not found.", file=sys.stderr)
            return 2
        cfg = load_yaml_config(yaml_path)
        validate_config(cfg)

        project_id = _get_project_id(args)
        if not project_id:
            print("error: project context is required.", file=sys.stderr)
            return 2

        # CI token specific run trigger
        token = _get_token()
        if token and token.startswith("airex_ci_"):
            # Prepare CI run payload
            # Parse git provenance where possible
            ci_run_id = os.environ.get("GITHUB_RUN_ID", os.environ.get("CI_PIPELINE_ID", str(uuid4())))
            ci_job_id = os.environ.get("GITHUB_JOB", os.environ.get("CI_JOB_ID"))
            commit_sha = os.environ.get("GITHUB_SHA", os.environ.get("CI_COMMIT_SHA", "local-dev"))
            branch = os.environ.get("GITHUB_REF_NAME", os.environ.get("CI_COMMIT_BRANCH", "local"))
            repo = os.environ.get("GITHUB_REPOSITORY", os.environ.get("CI_PROJECT_PATH", "local/project"))
            pr_num = os.environ.get("GITHUB_EVENT_PULL_REQUEST_NUMBER")
            pr_url = None
            if pr_num:
                pr_num = int(pr_num)
                pr_url = f"https://github.com/{repo}/pull/{pr_num}"

            # Compute idempotency key: repo + commit + hash(config) + ci_run_id
            cfg_hash = hashlib.sha256(yaml.safe_dump(cfg).encode()).hexdigest()
            idempotency_key = f"{repo}:{commit_sha}:{cfg_hash}:{ci_run_id}"

            payload = {
                "commit_sha": commit_sha,
                "branch": branch,
                "repository": repo,
                "pull_request_number": pr_num,
                "pull_request_url": pr_url,
                "ci_provider": "GITHUB_ACTIONS" if "GITHUB_ACTIONS" in os.environ else ("GITLAB_CI" if "GITLAB_CI" in os.environ else "GENERIC_CI"),
                "ci_run_id": ci_run_id,
                "ci_job_id": ci_job_id,
                "experiment_config": cfg,
                "idempotency_key": idempotency_key,
            }
            print("Triggering CI Run pipeline...", file=sys.stderr)
            resp = _request("POST", "/api/v1/ci/runs", json_data=payload)
            ci_data = resp.json().get("data", {})
            experiment_id = ci_data.get("experiment_id")
            run_id = ci_data.get("experiment_run_id")
        else:
            # Standard creation flow
            # Resolve Dataset
            exp_cfg = cfg.get("experiment") or {}
            dataset_name = exp_cfg.get("dataset")
            
            resp_datasets = _request("GET", f"/api/v1/projects/{project_id}/datasets")
            datasets = resp_datasets.json().get("data", [])
            dataset = next((d for d in datasets if d["name"] == dataset_name or d["slug"] == dataset_name), None)
            if not dataset:
                print(f"error: dataset '{dataset_name}' not found under project.", file=sys.stderr)
                return 4

            # Resolve latest dataset version
            resp_versions = _request("GET", f"/api/v1/datasets/{dataset['id']}/versions")
            versions = resp_versions.json().get("data", [])
            if not versions:
                print(f"error: dataset '{dataset_name}' has no active versions.", file=sys.stderr)
                return 2
            dataset_version_id = versions[0]["id"]

            # Resolve Models
            base_model_name = exp_cfg["baseline"]["model"]
            cand_model_name = exp_cfg["candidate"]["model"]

            resp_models = _request("GET", f"/api/v1/projects/{project_id}/models")
            models = resp_models.json().get("data", [])
            
            base_model = next((m for m in models if m["name"] == base_model_name or m["model_identifier"] == base_model_name), None)
            cand_model = next((m for m in models if m["name"] == cand_model_name or m["model_identifier"] == cand_model_name), None)

            if not base_model:
                print(f"error: baseline model '{base_model_name}' not found.", file=sys.stderr)
                return 4
            if not cand_model:
                print(f"error: candidate model '{cand_model_name}' not found.", file=sys.stderr)
                return 4

            gates_payload = []
            for gate in cfg.get("quality_gates", []):
                gates_payload.append({
                    "metric_name": gate["metric"],
                    "operator": gate["operator"].upper(),
                    "threshold": float(gate["threshold"]),
                    "severity": "SEVERE" if gate.get("required", True) else "MINOR",
                    "is_required": gate.get("required", True),
                    "gate_type": "CANDIDATE_VALUE",
                })

            payload = {
                "project_id": project_id,
                "name": f"CLI Run - {datetime.now(UTC).strftime('%Y%m%d%H%M')}",
                "description": "Triggered via AIREX CLI",
                "dataset_id": dataset["id"],
                "dataset_version_id": dataset_version_id,
                "baseline": {
                    "model_id": base_model["id"],
                    "prompt_content": exp_cfg["baseline"].get("prompt_content"),
                    "configuration": exp_cfg["baseline"].get("configuration") or {},
                },
                "candidate": {
                    "model_id": cand_model["id"],
                    "prompt_content": exp_cfg["candidate"].get("prompt_content"),
                    "configuration": exp_cfg["candidate"].get("configuration") or {},
                },
                "gates": gates_payload,
            }

            resp = _request("POST", f"/api/v1/projects/{project_id}/experiments", json_data=payload)
            experiment_id = resp.json().get("data", {}).get("id")

            # Start the run
            print(f"Starting experiment {experiment_id} run...", file=sys.stderr)
            run_resp = _request("POST", f"/api/v1/experiments/{experiment_id}/run")
            run_id = run_resp.json().get("data", {}).get("id")

    else:
        # ID was supplied: trigger run directly
        print(f"Starting experiment {experiment_id} run...", file=sys.stderr)
        run_resp = _request("POST", f"/api/v1/experiments/{experiment_id}/run")
        run_id = run_resp.json().get("data", {}).get("id")

    if not run_id:
        print("error: failed to start experiment run.", file=sys.stderr)
        return 6

    # 7. Polling loop
    poll_interval = args.poll_interval
    timeout = args.timeout
    start_time = time.time()
    
    print(f"Running Experiment Run ID: {run_id}. Polling for completion...", file=sys.stderr)
    
    while True:
        if time.time() - start_time > timeout:
            print("error: execution timed out.", file=sys.stderr)
            return 7

        resp_status = _request("GET", f"/api/v1/experiments/{experiment_id}/runs")
        runs = resp_status.json().get("data", [])
        current_run = next((r for r in runs if r["id"] == run_id), None)
        if not current_run:
            print(f"error: run '{run_id}' not found.", file=sys.stderr)
            return 4

        status = current_run.get("status")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            # Check gates results
            resp_gates = _request("GET", f"/api/v1/experiments/{run_id}/quality-gates")
            gates_res = resp_gates.json().get("data", [])
            
            # Print summary to stderr
            print("\nAIREX Experiment Execution Results", file=sys.stderr)
            print("=================================", file=sys.stderr)
            print(f"Run Status: {status}", file=sys.stderr)
            
            # Get comparisons list
            resp_comps = _request("GET", f"/api/v1/experiments/{run_id}/results")
            comps = resp_comps.json().get("data", [])
            
            print(f"\nComparisons metrics:", file=sys.stderr)
            for comp in comps:
                metric = comp["metric_name"]
                base_v = comp["baseline_value"]
                cand_v = comp["candidate_value"]
                diff = comp["absolute_difference"]
                rel = comp["relative_difference"]
                rel_str = f"{rel*100:+.1f}%" if rel is not None else "0.0%"
                print(f" - {metric}: Baseline={base_v}, Candidate={cand_v}, Diff={diff} ({rel_str})", file=sys.stderr)

            print(f"\nQuality Gates Checklists:", file=sys.stderr)
            gates_failed = False
            for g in gates_res:
                name = g["metric_name"]
                status_gate = g["status"]
                actual = g["actual_value"]
                # Load rule details
                print(f" - {name}: Actual={actual} ({status_gate})", file=sys.stderr)
                if status_gate == "FAIL":
                    gates_failed = True

            # If it's cancelled, exit with 8
            if status == "CANCELLED":
                print("Run cancelled.", file=sys.stderr)
                return 8

            # Return outcome
            if gates_failed or status == "FAILED":
                print("\nQuality Gate: FAILED", file=sys.stderr)
                # Output json if requested
                if getattr(args, "output", "table") == "json":
                    _output(args, {
                        "experiment_id": str(experiment_id),
                        "run_id": str(run_id),
                        "status": status,
                        "overall_result": "FAIL",
                        "quality_gate": {"status": "FAIL"},
                        "metrics": comps,
                    })
                return 1

            print("\nQuality Gate: PASSED", file=sys.stderr)
            if getattr(args, "output", "table") == "json":
                _output(args, {
                    "experiment_id": str(experiment_id),
                    "run_id": str(run_id),
                    "status": status,
                    "overall_result": "PASS",
                    "quality_gate": {"status": "PASS"},
                    "metrics": comps,
                })
            return 0

        time.sleep(poll_interval)


def cmd_experiment_status(args: argparse.Namespace) -> int:
    experiment_id = getattr(args, "id", None)
    if not experiment_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/experiments/{experiment_id}/runs")
    runs = resp.json().get("data", [])
    return _output(args, runs, ["id", "status", "created_at"])


def cmd_experiment_results(args: argparse.Namespace) -> int:
    run_id = getattr(args, "id", None)
    if not run_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/experiments/{run_id}/results")
    comps = resp.json().get("data", [])
    return _output(args, comps, ["metric_name", "baseline_value", "candidate_value", "absolute_difference", "classification"])


def cmd_experiment_cancel(args: argparse.Namespace) -> int:
    run_id = getattr(args, "id", None)
    if not run_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    _request("POST", f"/api/v1/experiments/{run_id}/cancel")
    print("Experiment run cancelled successfully.")
    return 0


def cmd_evaluations_run(args: argparse.Namespace) -> int:
    project_id = _get_project_id(args)
    if not project_id:
        print("error: project context is required.", file=sys.stderr)
        return 2
    # Simple trigger
    payload = {
        "project_id": project_id,
        "name": f"CLI Eval - {datetime.now(UTC).strftime('%Y%m%d%H%M')}",
    }
    resp = _request("POST", f"/api/v1/projects/{project_id}/evaluations", json_data=payload)
    print("Evaluation triggered.")
    return _output(args, resp.json().get("data", {}))


def cmd_evaluations_results(args: argparse.Namespace) -> int:
    run_id = getattr(args, "id", None)
    if not run_id:
        print("error: --id is required.", file=sys.stderr)
        return 2
    resp = _request("GET", f"/api/v1/evaluations/{run_id}/results")
    results = resp.json().get("data", [])
    return _output(args, results)


def cmd_benchmark_create(args: argparse.Namespace) -> int:
    yaml_path = Path(args.config)
    if not yaml_path.exists():
        print(f"error: config file '{args.config}' not found.", file=sys.stderr)
        return 2

    cfg = load_yaml_config(yaml_path)
    b_cfg = cfg.get("benchmark") or {}
    dataset_name = b_cfg.get("dataset")

    project_id = _get_project_id(args)
    if not project_id:
        print("error: project context is required.", file=sys.stderr)
        return 2

    resp_datasets = _request("GET", f"/api/v1/projects/{project_id}/datasets")
    datasets = resp_datasets.json().get("data", [])
    dataset = next((d for d in datasets if d["name"] == dataset_name or d["slug"] == dataset_name), None)
    if not dataset:
        print(f"error: dataset '{dataset_name}' not found.", file=sys.stderr)
        return 4

    resp_versions = _request("GET", f"/api/v1/datasets/{dataset['id']}/versions")
    versions = resp_versions.json().get("data", [])
    if not versions:
        print(f"error: dataset '{dataset_name}' has no active versions.", file=sys.stderr)
        return 2
    dataset_version_id = versions[0]["id"]

    payload = {
        "name": b_cfg.get("name", "Benchmark Suite"),
        "description": b_cfg.get("description"),
        "configuration": {
            "dataset_version_id": str(dataset_version_id),
            "baseline": b_cfg.get("baseline"),
            "candidates": b_cfg.get("candidates"),
            "weights": b_cfg.get("weights"),
            "evaluators": b_cfg.get("evaluators"),
        }
    }

    resp = _request("POST", f"/api/v1/projects/{project_id}/benchmarks", json_data=payload)
    if resp.status_code != 201:
        print(f"error: failed to create benchmark suite: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    print(f"Benchmark suite '{data.get('name')}' created successfully with ID: {data.get('id')}")
    return 0


def cmd_benchmark_run(args: argparse.Namespace) -> int:
    project_id = _get_project_id(args)
    suite_id = getattr(args, "id", None)

    if not suite_id:
        yaml_path = Path(args.config)
        if not yaml_path.exists():
            print("error: either --id or a valid --config file is required.", file=sys.stderr)
            return 2
        
        cfg = load_yaml_config(yaml_path)
        b_cfg = cfg.get("benchmark") or {}
        suite_name = b_cfg.get("name")

        if not project_id:
            print("error: project context is required.", file=sys.stderr)
            return 2

        resp_suites = _request("GET", f"/api/v1/projects/{project_id}/benchmarks")
        suites = resp_suites.json().get("data", [])
        suite = next((s for s in suites if s["name"] == suite_name), None)

        if suite:
            suite_id = suite["id"]
            dataset_name = b_cfg.get("dataset")
            resp_datasets = _request("GET", f"/api/v1/projects/{project_id}/datasets")
            datasets = resp_datasets.json().get("data", [])
            dataset = next((d for d in datasets if d["name"] == dataset_name or d["slug"] == dataset_name), None)
            if not dataset:
                print(f"error: dataset '{dataset_name}' not found.", file=sys.stderr)
                return 4

            resp_versions = _request("GET", f"/api/v1/datasets/{dataset['id']}/versions")
            versions = resp_versions.json().get("data", [])
            if not versions:
                print(f"error: dataset '{dataset_name}' has no active versions.", file=sys.stderr)
                return 2
            dataset_version_id = versions[0]["id"]

            version_payload = {
                "configuration": {
                    "dataset_version_id": str(dataset_version_id),
                    "baseline": b_cfg.get("baseline"),
                    "candidates": b_cfg.get("candidates"),
                    "weights": b_cfg.get("weights"),
                    "evaluators": b_cfg.get("evaluators"),
                }
            }
            _request("POST", f"/api/v1/benchmarks/{suite_id}/versions", json_data=version_payload)
        else:
            dataset_name = b_cfg.get("dataset")
            resp_datasets = _request("GET", f"/api/v1/projects/{project_id}/datasets")
            datasets = resp_datasets.json().get("data", [])
            dataset = next((d for d in datasets if d["name"] == dataset_name or d["slug"] == dataset_name), None)
            if not dataset:
                print(f"error: dataset '{dataset_name}' not found.", file=sys.stderr)
                return 4

            resp_versions = _request("GET", f"/api/v1/datasets/{dataset['id']}/versions")
            versions = resp_versions.json().get("data", [])
            if not versions:
                print(f"error: dataset '{dataset_name}' has no active versions.", file=sys.stderr)
                return 2
            dataset_version_id = versions[0]["id"]

            suite_payload = {
                "name": b_cfg.get("name", "Benchmark Suite"),
                "description": b_cfg.get("description"),
                "configuration": {
                    "dataset_version_id": str(dataset_version_id),
                    "baseline": b_cfg.get("baseline"),
                    "candidates": b_cfg.get("candidates"),
                    "weights": b_cfg.get("weights"),
                    "evaluators": b_cfg.get("evaluators"),
                }
            }
            resp_create = _request("POST", f"/api/v1/projects/{project_id}/benchmarks", json_data=suite_payload)
            if resp_create.status_code != 201:
                print(f"error: failed to create suite: {resp_create.text}", file=sys.stderr)
                return 5
            suite_id = resp_create.json()["data"]["id"]

    resp_run = _request("POST", f"/api/v1/benchmarks/{suite_id}/runs", json_data={})
    if resp_run.status_code != 201:
        print(f"error: failed to trigger run: {resp_run.text}", file=sys.stderr)
        return 5

    run_data = resp_run.json().get("data", {})
    run_id = run_data.get("id")
    print(f"Benchmark run triggered successfully. Run ID: {run_id}")

    poll_interval = getattr(args, "poll_interval", 3.0)
    timeout = getattr(args, "timeout", 600.0)
    
    start_time = time.time()
    print("Polling run status...")
    while True:
        resp_status = _request("GET", f"/api/v1/benchmarks/runs/{run_id}")
        run_detail = resp_status.json().get("data", {})
        status = run_detail.get("run", {}).get("status")
        
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            print(f"Benchmark run finished with status: {status}")
            if status == "COMPLETED":
                print(f"Overall Reliability Score: {run_detail.get('run', {}).get('reliability_score')}")
                return 0
            else:
                print(f"error: {run_detail.get('run', {}).get('error_message')}", file=sys.stderr)
                return 1
        
        if time.time() - start_time > timeout:
            print("error: execution timed out.", file=sys.stderr)
            return 3
            
        time.sleep(poll_interval)


def cmd_benchmark_status(args: argparse.Namespace) -> int:
    run_id = getattr(args, "id", None)
    if not run_id:
        print("error: --id is required.", file=sys.stderr)
        return 2
    
    resp = _request("GET", f"/api/v1/benchmarks/runs/{run_id}")
    if resp.status_code != 200:
        print(f"error: failed to fetch status: {resp.text}", file=sys.stderr)
        return 5

    run_detail = resp.json().get("data", {})
    run = run_detail.get("run", {})
    print(f"Run ID: {run.get('id')}")
    print(f"Status: {run.get('status')}")
    print(f"Reliability Score: {run.get('reliability_score')}")
    if run.get("error_message"):
        print(f"Error Message: {run.get('error_message')}")
    return 0


def cmd_benchmark_results(args: argparse.Namespace) -> int:
    run_id = getattr(args, "id", None)
    if not run_id:
        print("error: --id is required.", file=sys.stderr)
        return 2
    
    resp = _request("GET", f"/api/v1/benchmarks/runs/{run_id}")
    if resp.status_code != 200:
        print(f"error: failed to fetch results: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    run = data.get("run", {})
    results = data.get("results", [])
    evidences = data.get("evidences", [])
    clusters = data.get("clusters", [])
    rec = data.get("recommendation")

    print("======================================================================")
    print(f"BENCHMARK RUN RESULTS: {run.get('id')}")
    print(f"Status: {run.get('status')} | Overall Reliability Score: {run.get('reliability_score')}")
    print("======================================================================")
    
    print("\nCANDIDATE RESULTS:")
    print(f"{'Candidate Run ID':<38} | {'Model ID':<38} | {'Reliability Score':<18}")
    print("-" * 100)
    for r in results:
        print(f"{r.get('evaluation_run_id'):<38} | {r.get('model_id'):<38} | {r.get('reliability_score'):<18}")

    print("\nRELIABILITY EVIDENCE:")
    print(f"{'Metric Name':<20} | {'Baseline Value':<14} | {'Candidate Value':<15} | {'Absolute Change':<15} | {'Significance':<12} | {'Confidence':<10}")
    print("-" * 100)
    for ev in evidences:
        sig_str = "Yes" if ev.get("significance") else "No"
        print(f"{ev.get('metric_name'):<20} | {ev.get('baseline_value'):<14.4f} | {ev.get('candidate_value'):<15.4f} | {ev.get('absolute_change'):<15.4f} | {sig_str:<12} | {ev.get('confidence'):<10}")

    if clusters:
        print("\nFAILURE CLUSTERS:")
        print(f"{'Failure Type':<25} | {'Count':<5} | {'Percentage':<10} | {'Severity':<8} | {'Pattern'}")
        print("-" * 100)
        for cl in clusters:
            pct_str = f"{cl.get('cluster_percentage', 0.0) * 100:.1f}%"
            print(f"{cl.get('failure_type'):<25} | {cl.get('cluster_count'):<5} | {pct_str:<10} | {cl.get('severity'):<8} | {cl.get('error_message_pattern')}")

    if rec:
        print("\nROOT-CAUSE ANALYSIS & ACTIONABLE RECOMMENDATIONS:")
        if rec.get("regression_attribution"):
            print(f"Regression Attribution: {rec.get('regression_attribution')}")
        print(f"Root-Cause Analysis:    {rec.get('root_cause_analysis')}")
        print(f"Confidence Level:       {rec.get('root_cause_confidence')}")
        print(f"Actionable Recommendation: {rec.get('recommendation')}")
    
    return 0


def cmd_benchmark_reproduce(args: argparse.Namespace) -> int:
    run_id = getattr(args, "id", None)
    if not run_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/benchmarks/runs/{run_id}")
    if resp.status_code != 200:
        print(f"error: original run not found: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    run = data.get("run", {})
    suite_id = run.get("benchmark_suite_id")
    version_id = run.get("benchmark_version_id")

    payload = {
        "benchmark_version_id": version_id
    }
    resp_run = _request("POST", f"/api/v1/benchmarks/{suite_id}/runs", json_data=payload)
    if resp_run.status_code != 201:
        print(f"error: failed to trigger reproduction run: {resp_run.text}", file=sys.stderr)
        return 5

    new_run_data = resp_run.json().get("data", {})
    print(f"Reproduction run triggered successfully. Original Run: {run_id} | New Run: {new_run_data.get('id')}")
    return 0


def cmd_quality_gate_check(args: argparse.Namespace) -> int:
    results_file = getattr(args, "results", None)
    if results_file:
        # Local JSON results check mode
        try:
            res_path = Path(results_file)
            if not res_path.exists():
                print(f"error: results file '{results_file}' not found.", file=sys.stderr)
                return 4
            res_data = json.loads(res_path.read_text())
            overall = res_data.get("overall_result") or res_data.get("quality_gate", {}).get("status")
            if overall == "FAIL":
                print("Quality Gate: FAIL", file=sys.stderr)
                return 1
            print("Quality Gate: PASS", file=sys.stderr)
            return 0
        except Exception as exc:
            print(f"error: failed to load JSON results: {exc}", file=sys.stderr)
            return 2

    # Server API check mode
    experiment_id = getattr(args, "experiment", None)
    if not experiment_id:
        print("error: --experiment or --results parameter is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/experiments/{experiment_id}/quality-gates")
    gates = resp.json().get("data", [])
    
    gates_failed = False
    for g in gates:
        if g.get("status") == "FAIL":
            gates_failed = True

    if gates_failed:
        print("Quality Gate: FAIL", file=sys.stderr)
        return 1

    print("Quality Gate: PASS", file=sys.stderr)
    return 0


# ============================================================= Phase 10 Decision Commands

def _resolve_project_id_or_exit(args: argparse.Namespace) -> str:
    proj_id = _get_project_id(args)
    if not proj_id:
        print("error: --project-id is required or AIREX_PROJECT_ID must be set.", file=sys.stderr)
        sys.exit(2)
    return proj_id


def cmd_decision_create(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    env_id = getattr(args, "environment_id", None)
    model_id = getattr(args, "model_id", None)
    policy_id = getattr(args, "policy_id", None)

    if not env_id or not model_id or not policy_id:
        print("error: --environment-id, --model-id, and --policy-id are required.", file=sys.stderr)
        return 2

    payload = {
        "environment_id": env_id,
        "model_id": model_id,
        "release_policy_id": policy_id,
        "model_version": getattr(args, "model_version", None),
    }

    resp = _request("POST", f"/api/v1/projects/{project_id}/release-decisions", json_data=payload)
    if resp.status_code != 201:
        print(f"error: failed to create decision: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Created Release Decision: {data.get('id')}")
        print(f"Status: {data.get('status')} | Policy Version: {data.get('policy_version')}")
        print(f"Fingerprint: {data.get('configuration_fingerprint')}")
    return 0


def cmd_decision_evaluate(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("POST", f"/api/v1/projects/{project_id}/release-decisions/{decision_id}/evaluate")
    if resp.status_code != 200:
        print(f"error: failed to evaluate decision: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    outcome = data.get("outcome", "UNKNOWN")
    score = data.get("readiness_score")

    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print("======================================================================")
        print(f"RELEASE DECISION EVALUATION: {decision_id}")
        print(f"Outcome: {outcome} | Readiness Score: {score}/100")
        print("======================================================================")
        checks = data.get("checks", [])
        if checks:
            print(f"{'Rule Name':<30} | {'Status':<12} | {'Explanation'}")
            print("-" * 80)
            for c in checks:
                print(f"{c.get('rule_name'):<30} | {c.get('status'):<12} | {c.get('explanation')}")

    if outcome == "APPROVED":
        return 0
    elif outcome == "CONDITIONALLY_APPROVED":
        print("\nNotice: Decision conditionally approved with warnings.", file=sys.stderr)
        return 0
    elif outcome in ("REJECTED", "BLOCKED"):
        return 1
    elif outcome == "INSUFFICIENT_EVIDENCE":
        return 2
    return 1


def cmd_decision_status(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/projects/{project_id}/release-decisions/{decision_id}")
    if resp.status_code != 200:
        print(f"error: decision not found: {resp.text}", file=sys.stderr)
        return 4

    data = resp.json().get("data", {})
    outcome = data.get("outcome")
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Decision ID:      {data.get('id')}")
        print(f"Status:           {data.get('status')}")
        print(f"Outcome:          {outcome or 'PENDING EVALUATION'}")
        print(f"Readiness Score:  {data.get('readiness_score')}")
        print(f"Environment ID:   {data.get('environment_id')}")
        print(f"Model ID:         {data.get('model_id')}")
        print(f"Evaluated At:     {data.get('evaluated_at')}")

    if outcome == "APPROVED" or outcome == "CONDITIONALLY_APPROVED":
        return 0
    elif outcome in ("REJECTED", "BLOCKED"):
        return 1
    elif outcome == "INSUFFICIENT_EVIDENCE":
        return 2
    return 0


def cmd_decision_evidence(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/projects/{project_id}/release-decisions/{decision_id}/evidence")
    if resp.status_code != 200:
        print(f"error: failed to get evidence: {resp.text}", file=sys.stderr)
        return 5

    items = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(items, indent=2))
    else:
        if not items:
            print("No evidence records collected for this decision.")
            return 0
        print(f"{'Source Type':<16} | {'Source ID':<38} | {'Fresh':<6} | {'Freshness Timestamp'}")
        print("-" * 80)
        for it in items:
            fresh_str = "Yes" if it.get("is_fresh") else "No"
            print(f"{it.get('source_type'):<16} | {it.get('source_id'):<38} | {fresh_str:<6} | {it.get('freshness_timestamp')}")
    return 0


def cmd_decision_checks(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    resp = _request("GET", f"/api/v1/projects/{project_id}/release-decisions/{decision_id}/checks")
    if resp.status_code != 200:
        print(f"error: failed to get checks: {resp.text}", file=sys.stderr)
        return 5

    items = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(items, indent=2))
    else:
        if not items:
            print("No checks evaluated yet.")
            return 0
        print(f"{'Rule Name':<30} | {'Status':<10} | {'Blocking':<8} | {'Explanation'}")
        print("-" * 90)
        for it in items:
            blk_str = "Yes" if it.get("is_blocking") else "No"
            print(f"{it.get('rule_name'):<30} | {it.get('status'):<10} | {blk_str:<8} | {it.get('explanation')}")
    return 0


def cmd_decision_compare(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    decision_id = getattr(args, "id", None)
    if not decision_id:
        print("error: --id is required.", file=sys.stderr)
        return 2

    params = {}
    if getattr(args, "previous_id", None):
        params["previous_decision_id"] = args.previous_id

    resp = _request("GET", f"/api/v1/projects/{project_id}/release-decisions/{decision_id}/compare", params=params)
    if resp.status_code != 200:
        print(f"error: failed to compare decisions: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Comparison Summary: {data.get('summary')}")
        print(f"Compatible: {'Yes' if data.get('is_compatible') else 'No'}")
        metrics_list = data.get("metrics", [])
        if metrics_list:
            print(f"\n{'Metric':<24} | {'Previous':<14} | {'Current':<14} | {'Change Status':<12} | {'Explanation'}")
            print("-" * 90)
            for m in metrics_list:
                print(f"{m.get('metric_name'):<24} | {str(m.get('previous_value')):<14} | {str(m.get('current_value')):<14} | {m.get('change_status'):<12} | {m.get('explanation')}")
    return 0


def cmd_intelligence_overview(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)

    resp = _request("GET", f"/api/v1/projects/{project_id}/intelligence/overview")
    if resp.status_code != 200:
        print(f"error: failed to fetch intelligence overview: {resp.text}", file=sys.stderr)
        return 5

    data = resp.json().get("data", {})
    overall_status = data.get("overall_status", "UNKNOWN")
    readiness = data.get("readiness_score")

    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print("======================================================================")
        print(f"PROJECT INTELLIGENCE OVERVIEW: {project_id}")
        print(f"Overall Status: {overall_status} | Latest Readiness Score: {readiness if readiness is not None else 'N/A'}")
        print("======================================================================")

        blocking = data.get("blocking_issues", [])
        if blocking:
            print("\nBlocking Issues:")
            for b in blocking:
                print(f"  ❌ {b}")

        warnings = data.get("warnings", [])
        if warnings:
            print("\nWarnings:")
            for w in warnings:
                print(f"  ⚠️ {w}")

        models = data.get("model_comparisons", [])
        if models:
            print(f"\n{'Model':<30} | {'Readiness Score':<16} | {'Latest Outcome'}")
            print("-" * 65)
            for m in models:
                score_str = str(m.get('readiness_score')) if m.get('readiness_score') is not None else "N/A"
                print(f"{m.get('name'):<30} | {score_str:<16} | {m.get('latest_outcome')}")

    if overall_status == "READY" or overall_status == "AT_RISK":
        return 0
    elif overall_status == "BLOCKED":
        return 1
    return 2


# ============================================================= Phase 11 Agents CLI Commands

def cmd_agents_create(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    payload = {
        "name": args.name,
        "description": getattr(args, "description", None),
        "agent_type": getattr(args, "agent_type", "TOOL_AGENT"),
        "system_prompt": getattr(args, "prompt", None),
    }
    resp = _request("POST", f"/api/v1/projects/{project_id}/agents", json=payload)
    if resp.status_code != 201:
        print(f"error: failed to create agent: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"✅ Created agent '{data.get('name')}' (ID: {data.get('id')}, Version: {data.get('version')})")
    return 0


def cmd_agents_list(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    resp = _request("GET", f"/api/v1/projects/{project_id}/agents")
    if resp.status_code != 200:
        print(f"error: failed to list agents: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Name':<24} | {'Type':<14} | {'Ver':<4} | {'Active'}")
        print("-" * 90)
        for a in data:
            print(f"{a.get('id'):<36} | {a.get('name'):<24} | {a.get('agent_type'):<14} | {a.get('version'):<4} | {'Yes' if a.get('is_active') else 'No'}")
    return 0


def cmd_agents_run(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    agent_id = args.agent_id
    payload: dict[str, Any] = {}
    if getattr(args, "env_id", None):
        payload["environment_id"] = args.env_id
    if getattr(args, "task", None):
        try:
            payload["task"] = json.loads(args.task)
        except Exception:
            payload["task"] = {"task_id": "cli_task", "instruction": args.task}
    resp = _request("POST", f"/api/v1/projects/{project_id}/agents/{agent_id}/runs", json=payload)
    if resp.status_code != 201:
        print(f"error: failed to start agent run: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Agent Run ID: {data.get('id')}")
        print(f"Status: {data.get('status')} | Goal: {data.get('goal_completion_status')}")
        print(f"Steps: {data.get('total_steps')} | Tool Calls: {data.get('total_tool_calls')}")
        print(f"Reliability Score: {data.get('reliability_score')}")
    status = data.get("status")
    return 0 if status in ("COMPLETED", "RUNNING") else 1


def cmd_agents_status(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    run_id = args.run_id
    resp = _request("GET", f"/api/v1/projects/{project_id}/agent-runs/{run_id}")
    if resp.status_code != 200:
        print(f"error: failed to get agent run status: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Run ID: {data.get('id')}")
        print(f"Agent ID: {data.get('agent_id')} (v{data.get('agent_version')})")
        print(f"Status: {data.get('status')} | Goal: {data.get('goal_completion_status')}")
        print(f"Reliability Score: {data.get('reliability_score')}")
        print(f"Loops Detected: {data.get('loops_detected')} | Safety Violations: {data.get('safety_violations')}")
    status = data.get("status")
    return 0 if status == "COMPLETED" else (1 if status == "FAILED" else 2)


def cmd_agents_trajectory(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    run_id = args.run_id
    resp = _request("GET", f"/api/v1/projects/{project_id}/agent-runs/{run_id}/trajectory")
    if resp.status_code != 200:
        print(f"error: failed to get trajectory: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'Step':<5} | {'Type':<15} | {'Tool / Content':<30} | {'Status'}")
        print("-" * 75)
        for s in data:
            desc = s.get('tool_name') or (s.get('model_output') or s.get('model_input') or "")[:28]
            print(f"{s.get('step_number'):<5} | {s.get('step_type'):<15} | {desc:<30} | {s.get('status')}")
    return 0


def cmd_agents_evaluate(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    run_id = args.run_id
    resp = _request("POST", f"/api/v1/projects/{project_id}/agent-runs/{run_id}/evaluate")
    if resp.status_code != 200:
        print(f"error: failed to evaluate agent run: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    overall_status = data.get("overall_status", "UNKNOWN")
    score = data.get("reliability_score")
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Evaluation Outcome: {overall_status} | Reliability Score: {score}")
        print(f"Loops: {data.get('loops_detected')} | Safety Violations: {data.get('safety_violations')}")
        checks = data.get("checks", [])
        if checks:
            print(f"\n{'Check Name':<30} | {'Status':<8} | {'Explanation'}")
            print("-" * 80)
            for c in checks:
                print(f"{c.get('check_name'):<30} | {c.get('status'):<8} | {c.get('explanation')}")
    return 0 if overall_status in ("PASS", "WARNING") else 1


def cmd_agents_benchmark(args: argparse.Namespace) -> int:
    project_id = _resolve_project_id_or_exit(args)
    agent_id = args.agent_id
    resp = _request("GET", f"/api/v1/projects/{project_id}/agent-runs?agent_id={agent_id}")
    if resp.status_code != 200:
        print(f"error: failed to fetch agent benchmark runs: {resp.text}", file=sys.stderr)
        return 5
    runs = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(runs, indent=2))
    else:
        total = len(runs)
        completed = sum(1 for r in runs if r.get("goal_completion_status") == "COMPLETED")
        avg_score = (sum(r.get("reliability_score") or 0.0 for r in runs) / total) if total > 0 else 0.0
        print(f"AGENT BENCHMARK SUMMARY (Agent ID: {agent_id})")
        print(f"Total Evaluated Tasks: {total}")
        print(f"Goal Completion Rate: {completed}/{total} ({(completed/total*100.0 if total>0 else 0.0):.1f}%)")
        print(f"Average Reliability Score: {avg_score:.2f}/100")
    return 0


# ============================================================= Phase 12 System Handlers

def cmd_system_status(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/system/readiness")
    if resp.status_code != 200:
        print(f"error: failed to query system status: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    if getattr(args, "json", False) or getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        status = data.get("overall_status", "UNKNOWN")
        color_tag = "✓" if status == "HEALTHY" else ("!" if status == "DEGRADED" else "✗")
        print(f"AIREX System Status: {color_tag} {status}")
        print(f"Version: {data.get('version')} | Env: {data.get('environment')}")
        print("-" * 60)
        for check in data.get("checks", []):
            st = check.get("status")
            tag = "[OK]" if st == "HEALTHY" else f"[{st}]"
            print(f"{check.get('name'):<22} {tag:<12} {check.get('description')}")
    return 0


def cmd_system_readiness(args: argparse.Namespace) -> int:
    return cmd_system_status(args)


def cmd_system_version(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/system/schema-version")
    if resp.status_code != 200:
        print(f"error: failed to query schema version: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    if getattr(args, "json", False) or getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"AIREX Software Version: {__version__}")
        print(f"Active Migration Head: {data.get('current_version')}")
        print(f"Expected Head:        {data.get('expected_head')}")
        print(f"Schema Status:        {data.get('status')}")
    return 0


def cmd_system_workers(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/system/workers")
    if resp.status_code != 200:
        print(f"error: failed to query workers: {resp.text}", file=sys.stderr)
        return 5
    workers = resp.json().get("data", [])
    if getattr(args, "json", False) or getattr(args, "output", "table") == "json":
        print(json.dumps(workers, indent=2))
    else:
        print(f"{'Worker ID':<35} | {'Hostname':<15} | {'PID':<6} | {'Status':<8} | {'Jobs':<4} | {'Age (s)'}")
        print("-" * 80)
        for w in workers:
            print(f"{w.get('worker_id'):<35} | {w.get('hostname')[:14]:<15} | {w.get('pid'):<6} | {w.get('status'):<8} | {w.get('active_jobs_count'):<4} | {w.get('heartbeat_age_seconds')}")
        if not workers:
            print("No active worker heartbeats found.")
    return 0


def cmd_system_backup(args: argparse.Namespace) -> int:
    from app.services.backup_service import BackupService
    try:
        res = BackupService.create_backup(getattr(args, "output", None))
        if getattr(args, "json", False) or getattr(args, "output", "table") == "json":
            print(json.dumps(res, indent=2))
        else:
            print(f"Backup created successfully!")
            print(f"File:     {res.get('backup_file')}")
            print(f"SHA-256:  {res.get('checksum_sha256')}")
            print(f"Size:     {res.get('size_bytes')} bytes")
        return 0
    except Exception as exc:
        print(f"error: backup failed: {exc}", file=sys.stderr)
        return 1


def cmd_system_verify_backup(args: argparse.Namespace) -> int:
    from app.services.backup_service import BackupService
    try:
        res = BackupService.verify_backup(args.path)
        if getattr(args, "json", False) or getattr(args, "output", "table") == "json":
            print(json.dumps(res, indent=2))
        else:
            status = res.get("status")
            print(f"Backup Verification: {status}")
            print(f"File:     {res.get('backup_file')}")
            print(f"SHA-256:  {res.get('checksum_sha256')}")
            print(f"Size:     {res.get('size_bytes')} bytes")
            print(f"Valid:    {res.get('valid')}")
        return 0 if res.get("valid") else 1
    except Exception as exc:
        print(f"error: verification failed: {exc}", file=sys.stderr)
        return 1


# ============================================================= Phase 13 Enterprise Handlers

def _get_org_headers(args: argparse.Namespace) -> dict:
    org_id = getattr(args, "org_id", None) or os.environ.get("AIREX_ORGANIZATION_ID")
    return {"X-Organization-Id": org_id} if org_id else {}


def cmd_enterprise_identity_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/identity-providers", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list identity providers: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Name':<20} | {'Type':<8} | {'Status':<10} | {'Default Role'}")
        print("-" * 90)
        for i in data:
            print(f"{i.get('id'):<36} | {i.get('name'):<20} | {i.get('provider_type'):<8} | {i.get('status'):<10} | {i.get('default_role')}")
    return 0


def cmd_enterprise_identity_create(args: argparse.Namespace) -> int:
    payload = {
        "name": args.name,
        "provider_type": getattr(args, "provider_type", "OIDC"),
        "client_id": getattr(args, "client_id", None),
        "client_secret": getattr(args, "client_secret", None),
    }
    resp = _request("POST", "/api/v1/identity-providers", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create identity provider: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"Created Identity Provider: {data.get('id')} ({data.get('name')})")
        print(f"Status: {data.get('status')} | Masked Secret: {data.get('masked_client_secret')}")
    return 0


def cmd_enterprise_identity_enable(args: argparse.Namespace) -> int:
    resp = _request("PATCH", f"/api/v1/identity-providers/{args.idp_id}/status?status_val=ACTIVE", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to enable identity provider: {resp.text}", file=sys.stderr)
        return 5
    print(f"Identity Provider {args.idp_id} status set to ACTIVE")
    return 0


def cmd_enterprise_identity_disable(args: argparse.Namespace) -> int:
    resp = _request("PATCH", f"/api/v1/identity-providers/{args.idp_id}/status?status_val=DISABLED", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to disable identity provider: {resp.text}", file=sys.stderr)
        return 5
    print(f"Identity Provider {args.idp_id} status set to DISABLED")
    return 0


def cmd_enterprise_domains_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/domains", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list domains: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Domain':<25} | {'Status':<10} | {'Primary'}")
        print("-" * 80)
        for d in data:
            print(f"{d.get('id'):<36} | {d.get('domain'):<25} | {d.get('status'):<10} | {d.get('is_primary')}")
    return 0


def cmd_enterprise_domains_verify(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/domains/{args.domain_id}/verify", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to verify domain: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    print(f"Domain {data.get('domain')} verified successfully! Status: {data.get('status')}")
    return 0


def cmd_enterprise_teams_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/teams", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list teams: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Name':<20} | {'Slug':<20} | {'Members':<8} | {'Projects'}")
        print("-" * 95)
        for t in data:
            print(f"{t.get('id'):<36} | {t.get('name'):<20} | {t.get('slug'):<20} | {t.get('members_count', 0):<8} | {t.get('projects_count', 0)}")
    return 0


def cmd_enterprise_teams_create(args: argparse.Namespace) -> int:
    payload = {"name": args.name, "description": getattr(args, "description", None)}
    resp = _request("POST", "/api/v1/teams", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create team: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    print(f"Created Team: {data.get('id')} ({data.get('name')})")
    return 0


def cmd_enterprise_teams_members(args: argparse.Namespace) -> int:
    resp = _request("GET", f"/api/v1/teams/{args.team_id}/members", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list team members: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'User ID':<36} | {'Role':<10} | {'Email'}")
        print("-" * 75)
        for m in data:
            print(f"{m.get('user_id'):<36} | {m.get('role'):<10} | {m.get('user_email')}")
    return 0


def cmd_enterprise_tokens_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/ci/tokens", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list service tokens: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Name':<20} | {'Prefix':<10} | {'Status'}")
        print("-" * 80)
        for t in data:
            st = "REVOKED" if t.get("revoked_at") else "ACTIVE"
            print(f"{t.get('id'):<36} | {t.get('name'):<20} | {t.get('token_prefix'):<10} | {st}")
    return 0


def cmd_enterprise_tokens_revoke(args: argparse.Namespace) -> int:
    resp = _request("DELETE", f"/api/v1/ci/tokens/{args.token_id}", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to revoke token: {resp.text}", file=sys.stderr)
        return 5
    print(f"Service token {args.token_id} revoked successfully.")
    return 0


def cmd_enterprise_policies_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/governance-policies", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list governance policies: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Name':<25} | {'Ver':<4} | {'Status'}")
        print("-" * 75)
        for p in data:
            print(f"{p.get('id'):<36} | {p.get('name'):<25} | {p.get('version'):<4} | {p.get('status')}")
    return 0


def cmd_enterprise_policies_create(args: argparse.Namespace) -> int:
    payload = {"name": args.name, "description": getattr(args, "description", None)}
    resp = _request("POST", "/api/v1/governance-policies", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create policy: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    print(f"Created Governance Policy: {data.get('id')} ({data.get('name')} v{data.get('version')})")
    return 0


def cmd_enterprise_policies_activate(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/governance-policies/{args.policy_id}/activate", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to activate policy: {resp.text}", file=sys.stderr)
        return 5
    print(f"Governance policy {args.policy_id} activated successfully.")
    return 0


def cmd_enterprise_approvals_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/approvals", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list approval requests: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Target':<18} | {'Title':<25} | {'Status'}")
        print("-" * 90)
        for a in data:
            print(f"{a.get('id'):<36} | {a.get('target_type'):<18} | {a.get('title'):<25} | {a.get('status')}")
    return 0


def cmd_enterprise_approvals_approve(args: argparse.Namespace) -> int:
    payload = {"outcome": "APPROVED", "comments": getattr(args, "comments", "Approved via CLI")}
    resp = _request("POST", f"/api/v1/approvals/{args.request_id}/action", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: approval failed: {resp.text}", file=sys.stderr)
        return 5
    print(f"Approval request {args.request_id} has been APPROVED.")
    return 0


def cmd_enterprise_approvals_reject(args: argparse.Namespace) -> int:
    payload = {"outcome": "REJECTED", "comments": getattr(args, "comments", "Rejected via CLI")}
    resp = _request("POST", f"/api/v1/approvals/{args.request_id}/action", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: rejection failed: {resp.text}", file=sys.stderr)
        return 5
    print(f"Approval request {args.request_id} has been REJECTED.")
    return 0


def cmd_enterprise_access_review_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/access-reviews", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list access reviews: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", [])
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"{'ID':<36} | {'Title':<30} | {'Status':<12} | {'Items'}")
        print("-" * 88)
        for r in data:
            items_count = len(r.get("items", []))
            print(f"{r.get('id'):<36} | {r.get('title'):<30} | {r.get('status'):<12} | {items_count}")
    return 0


def cmd_enterprise_access_review_create(args: argparse.Namespace) -> int:
    payload = {"title": args.title}
    resp = _request("POST", "/api/v1/access-reviews", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create access review: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json().get("data", {})
    print(f"Created Access Review: {data.get('id')} ('{data.get('title')}') with {len(data.get('items', []))} items")
    return 0


def cmd_enterprise_access_review_complete(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/access-reviews/{args.review_id}/complete", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to complete access review: {resp.text}", file=sys.stderr)
        return 5
    print(f"Access review {args.review_id} COMPLETED and revocations executed.")
    return 0


# ============================================================= Phase 14 Compliance Handlers

def _print_or_json(data: Any, args: argparse.Namespace) -> None:
    if getattr(args, "output", "table") == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, list):
            print(f"Total: {len(data)} items")
            for item in data[:20]:
                print(f" - {item}")
        else:
            print(json.dumps(data, indent=2, default=str))


def cmd_compliance_framework_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/compliance/frameworks", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list frameworks: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_framework_create(args: argparse.Namespace) -> int:
    payload = {"name": args.name, "description": args.description}
    resp = _request("POST", "/api/v1/compliance/frameworks", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create framework: {resp.text}", file=sys.stderr)
        return 5
    print(f"Created Framework: {resp.json().get('id')} ({resp.json().get('name')})")
    return 0


def cmd_compliance_framework_activate(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/compliance/frameworks/{args.framework_id}/activate", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to activate framework: {resp.text}", file=sys.stderr)
        return 5
    print(f"Activated Framework {args.framework_id} (IMMUTABLE LOCKED).")
    return 0


def cmd_compliance_control_list(args: argparse.Namespace) -> int:
    resp = _request("GET", f"/api/v1/compliance/frameworks/{args.framework_id}/controls", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list controls: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_control_create(args: argparse.Namespace) -> int:
    payload = {
        "control_id": args.control_id,
        "title": args.title,
        "category": getattr(args, "category", None) or "GOVERNANCE",
        "risk_level": getattr(args, "risk_level", None) or "MEDIUM",
        "description": args.description,
    }
    resp = _request("POST", f"/api/v1/compliance/frameworks/{args.framework_id}/controls", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create control: {resp.text}", file=sys.stderr)
        return 5
    print(f"Created Control: {resp.json().get('control_id')} ({resp.json().get('title')})")
    return 0


def cmd_compliance_evidence_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/compliance/evidence", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list evidence: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_evidence_record(args: argparse.Namespace) -> int:
    payload = {
        "source_type": args.source_type,
        "source_id": args.source_id,
        "project_id": getattr(args, "project_id", None),
    }
    resp = _request("POST", "/api/v1/compliance/evidence", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to record evidence: {resp.text}", file=sys.stderr)
        return 5
    print(f"Recorded Evidence: {resp.json().get('id')} [SHA256: {resp.json().get('sha256_fingerprint')[:12]}...]")
    return 0


def cmd_compliance_evidence_verify(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/compliance/evidence/{args.evidence_id}/verify", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to verify evidence: {resp.text}", file=sys.stderr)
        return 5
    print(f"Evidence {args.evidence_id} integrity: {resp.json().get('integrity_status')} (Freshness: {resp.json().get('freshness_status')})")
    return 0


def cmd_compliance_assessment_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/compliance/assessments", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list assessments: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_assessment_create(args: argparse.Namespace) -> int:
    payload = {"framework_id": args.framework_id, "title": args.title}
    resp = _request("POST", "/api/v1/compliance/assessments", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create assessment: {resp.text}", file=sys.stderr)
        return 5
    print(f"Created Assessment: {resp.json().get('id')} ({resp.json().get('title')})")
    return 0


def cmd_compliance_assessment_run(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/compliance/assessments/{args.assessment_id}/run", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to run assessment: {resp.text}", file=sys.stderr)
        return 5
    print(f"Assessment {args.assessment_id} EXECUTED. Score: {resp.json().get('overall_score')}% ({resp.json().get('status')})")
    return 0


def cmd_compliance_assessment_approve(args: argparse.Namespace) -> int:
    payload = {"action": "APPROVE", "comment": getattr(args, "comment", None)}
    resp = _request("POST", f"/api/v1/compliance/assessments/{args.assessment_id}/action", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to approve assessment: {resp.text}", file=sys.stderr)
        return 5
    print(f"Assessment {args.assessment_id} APPROVED.")
    return 0


def cmd_compliance_assessment_reject(args: argparse.Namespace) -> int:
    payload = {"action": "REJECT", "comment": getattr(args, "comment", None)}
    resp = _request("POST", f"/api/v1/compliance/assessments/{args.assessment_id}/action", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to reject assessment: {resp.text}", file=sys.stderr)
        return 5
    print(f"Assessment {args.assessment_id} REJECTED.")
    return 0


def cmd_compliance_remediation_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/compliance/remediations", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list remediations: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_remediation_create(args: argparse.Namespace) -> int:
    payload = {
        "control_id": args.control_id,
        "title": args.title,
        "description": args.description,
        "severity": getattr(args, "severity", None) or "MEDIUM",
    }
    resp = _request("POST", "/api/v1/compliance/remediations", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create remediation: {resp.text}", file=sys.stderr)
        return 5
    print(f"Created Remediation: {resp.json().get('id')} ({resp.json().get('title')})")
    return 0


def cmd_compliance_remediation_resolve(args: argparse.Namespace) -> int:
    payload = {"resolution_notes": args.notes}
    resp = _request("POST", f"/api/v1/compliance/remediations/{args.remediation_id}/resolve", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to resolve remediation: {resp.text}", file=sys.stderr)
        return 5
    print(f"Remediation {args.remediation_id} RESOLVED.")
    return 0


def cmd_compliance_remediation_accept_risk(args: argparse.Namespace) -> int:
    payload = {"justification": args.justification}
    resp = _request("POST", f"/api/v1/compliance/remediations/{args.remediation_id}/accept-risk", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to accept risk: {resp.text}", file=sys.stderr)
        return 5
    print(f"Remediation {args.remediation_id} Risk Accepted.")
    return 0


def cmd_compliance_retention_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/compliance/retention", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list retention policies: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_retention_create(args: argparse.Namespace) -> int:
    payload = {"resource_type": args.resource_type, "retention_days": int(args.days), "description": args.description}
    resp = _request("POST", "/api/v1/compliance/retention", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create retention policy: {resp.text}", file=sys.stderr)
        return 5
    print(f"Created Retention Policy: {resp.json().get('resource_type')} -> {resp.json().get('retention_days')} days")
    return 0


def cmd_compliance_retention_cleanup(args: argparse.Namespace) -> int:
    payload = {"dry_run": args.dry_run}
    resp = _request("POST", "/api/v1/compliance/retention/cleanup", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to execute retention cleanup: {resp.text}", file=sys.stderr)
        return 5
    data = resp.json()
    print(f"Retention Cleanup [Dry Run: {data.get('dry_run')}]: Deleted: {data.get('deleted_records')}, Protected by Legal Hold: {data.get('protected_by_legal_hold')}")
    return 0


def cmd_compliance_legal_hold_list(args: argparse.Namespace) -> int:
    resp = _request("GET", "/api/v1/compliance/legal-holds", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to list legal holds: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json(), args)
    return 0


def cmd_compliance_legal_hold_create(args: argparse.Namespace) -> int:
    payload = {
        "title": args.title,
        "resource_type": args.resource_type,
        "target_resource_id": args.target_id,
        "reason": args.reason,
    }
    resp = _request("POST", "/api/v1/compliance/legal-holds", json_data=payload, headers=_get_org_headers(args))
    if resp.status_code != 201:
        print(f"error: failed to create legal hold: {resp.text}", file=sys.stderr)
        return 5
    print(f"Placed Legal Hold: {resp.json().get('id')} ({resp.json().get('title')}) on {resp.json().get('resource_type')}:{resp.json().get('target_resource_id')}")
    return 0


def cmd_compliance_legal_hold_release(args: argparse.Namespace) -> int:
    resp = _request("POST", f"/api/v1/compliance/legal-holds/{args.hold_id}/release", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to release legal hold: {resp.text}", file=sys.stderr)
        return 5
    print(f"Released Legal Hold {args.hold_id}.")
    return 0


def cmd_compliance_audit_list(args: argparse.Namespace) -> int:
    params = []
    if getattr(args, "category", None): params.append(f"category={args.category}")
    if getattr(args, "limit", None): params.append(f"limit={args.limit}")
    query_str = ("?" + "&".join(params)) if params else ""
    resp = _request("GET", f"/api/v1/compliance/audit/timeline{query_str}", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to query audit timeline: {resp.text}", file=sys.stderr)
        return 5
    _print_or_json(resp.json().get("events", []), args)
    return 0


def cmd_compliance_report_export(args: argparse.Namespace) -> int:
    resp = _request("GET", f"/api/v1/compliance/reports/export?assessment_id={args.assessment_id}&format={args.format}", headers=_get_org_headers(args))
    if resp.status_code != 200:
        print(f"error: failed to export compliance report: {resp.text}", file=sys.stderr)
        return 5
    print(resp.text)
    return 0


# ============================================================= Argument Parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="airex", description="AIREX CLI Command Center")
    parser.add_argument("--non-interactive", action="store_true", help="run in non-interactive CI mode")
    parser.add_argument("--output", choices=["table", "json", "quiet"], default="table", help="select layout format")
    
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print version")
    sub.add_parser("health", help="check API health")
    
    # Init
    init = sub.add_parser("init", help="create a default config template")
    init.add_argument("--project", help="project name/slug")
    init.add_argument("--dataset", help="dataset version target")
    init.add_argument("--baseline-model", help="baseline model ID")
    init.add_argument("--candidate-model", help="candidate model ID")

    # Auth
    auth = sub.add_parser("auth", help="authenticate options")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)
    login = auth_sub.add_parser("login", help="authenticate with email and password")
    login.add_argument("--email")
    login.add_argument("--password")
    auth_sub.add_parser("logout", help="clear credentials")
    auth_sub.add_parser("status", help="check connection profile")

    # Projects
    projects = sub.add_parser("projects", help="projects command settings")
    projects_sub = projects.add_subparsers(dest="projects_command", required=True)
    projects_sub.add_parser("list", help="list organizations projects")
    current_proj = projects_sub.add_parser("current", help="get active project context")
    current_proj.add_argument("--project-id")

    # Datasets
    datasets = sub.add_parser("datasets", help="datasets list/actions")
    datasets_sub = datasets.add_subparsers(dest="datasets_command", required=True)
    datasets_sub.add_parser("list", help="list datasets under current project")
    datasets_sub.add_parser("validate", help="validate configuration yaml file rules")

    # Experiments
    experiments = sub.add_parser("experiments", help="experiments configurations and comparisons")
    experiments_sub = experiments.add_subparsers(dest="experiments_command", required=True)
    
    create_exp = experiments_sub.add_parser("create", help="register an experiment from config")
    create_exp.add_argument("--config", default="airex.yaml", help="YAML file path")
    create_exp.add_argument("--project-id")

    run_exp = experiments_sub.add_parser("run", help="execute benchmarking run")
    run_exp.add_argument("--config", default="airex.yaml", help="YAML file path")
    run_exp.add_argument("--id", help="trigger direct experiment run by ID")
    run_exp.add_argument("--project-id")
    run_exp.add_argument("--poll-interval", type=float, default=3.0, help="interval in seconds")
    run_exp.add_argument("--timeout", type=float, default=600.0, help="execution timeout in seconds")

    status_exp = experiments_sub.add_parser("status", help="get status of experiment runs")
    status_exp.add_argument("--id", required=True, help="experiment ID")

    results_exp = experiments_sub.add_parser("results", help="get comparisons metrics results")
    results_exp.add_argument("--id", required=True, help="experiment run ID")

    cancel_exp = experiments_sub.add_parser("cancel", help="terminate run job")
    cancel_exp.add_argument("--id", required=True, help="experiment run ID")

    # Evaluations
    evaluations = sub.add_parser("evaluations", help="trigger evaluations runs")
    evaluations_sub = evaluations.add_subparsers(dest="evaluations_command", required=True)
    
    run_eval = evaluations_sub.add_parser("run", help="run evaluation suite")
    run_eval.add_argument("--project-id")
    
    res_eval = evaluations_sub.add_parser("results", help="fetch results by run ID")
    res_eval.add_argument("--id", required=True, help="run ID")

    # Benchmarks
    benchmarks = sub.add_parser("benchmarks", help="benchmark suite configurations, runs, and reliability analysis")
    benchmarks_sub = benchmarks.add_subparsers(dest="benchmarks_command", required=True)
    
    create_bench = benchmarks_sub.add_parser("create", help="register a benchmark suite from config")
    create_bench.add_argument("--config", default="benchmark.yaml", help="YAML file path")
    create_bench.add_argument("--project-id")

    run_bench = benchmarks_sub.add_parser("run", help="execute benchmarking run")
    run_bench.add_argument("--config", default="benchmark.yaml", help="YAML file path")
    run_bench.add_argument("--id", help="trigger direct benchmark run by ID")
    run_bench.add_argument("--project-id")
    run_bench.add_argument("--poll-interval", type=float, default=3.0, help="interval in seconds")
    run_bench.add_argument("--timeout", type=float, default=600.0, help="execution timeout in seconds")

    status_bench = benchmarks_sub.add_parser("status", help="get status of benchmark runs")
    status_bench.add_argument("--id", required=True, help="benchmark run ID")

    results_bench = benchmarks_sub.add_parser("results", help="get detailed benchmark run results")
    results_bench.add_argument("--id", required=True, help="benchmark run ID")

    reproduce_bench = benchmarks_sub.add_parser("reproduce", help="reproduce a benchmark run from its history")
    reproduce_bench.add_argument("--id", required=True, help="benchmark run ID to reproduce")
    reproduce_bench.add_argument("--project-id")

    # Quality Gate
    gate = sub.add_parser("quality-gate", help="quality gate policy checker")
    gate_sub = gate.add_subparsers(dest="gate_command", required=True)
    check_gate = gate_sub.add_parser("check", help="verify quality metrics gates status")
    check_gate.add_argument("--experiment", help="experiment ID on server")
    check_gate.add_argument("--results", help="path to local JSON results file")

    # Decisions (Phase 10)
    decision = sub.add_parser("decision", help="release and deployment decisions")
    decision_sub = decision.add_subparsers(dest="decision_command", required=True)

    dec_create = decision_sub.add_parser("create", help="create a release decision")
    dec_create.add_argument("--project-id")
    dec_create.add_argument("--environment-id", required=True, help="target environment UUID")
    dec_create.add_argument("--model-id", required=True, help="target model UUID")
    dec_create.add_argument("--policy-id", required=True, help="target release policy UUID")
    dec_create.add_argument("--model-version", help="optional model version")

    dec_eval = decision_sub.add_parser("evaluate", help="evaluate a release decision")
    dec_eval.add_argument("--id", required=True, help="release decision UUID")
    dec_eval.add_argument("--project-id")

    dec_status = decision_sub.add_parser("status", help="get release decision status")
    dec_status.add_argument("--id", required=True, help="release decision UUID")
    dec_status.add_argument("--project-id")

    dec_ev = decision_sub.add_parser("evidence", help="get canonical evidence for a decision")
    dec_ev.add_argument("--id", required=True, help="release decision UUID")
    dec_ev.add_argument("--project-id")

    dec_checks = decision_sub.add_parser("checks", help="get individual checks for a decision")
    dec_checks.add_argument("--id", required=True, help="release decision UUID")
    dec_checks.add_argument("--project-id")

    dec_comp = decision_sub.add_parser("compare", help="compare a decision against previous baseline")
    dec_comp.add_argument("--id", required=True, help="release decision UUID")
    dec_comp.add_argument("--previous-id", help="optional previous decision UUID")
    dec_comp.add_argument("--project-id")

    # Intelligence (Phase 10)
    intelligence = sub.add_parser("intelligence", help="executive project health intelligence")
    intelligence_sub = intelligence.add_subparsers(dest="intelligence_command", required=True)

    intel_overview = intelligence_sub.add_parser("overview", help="get executive project intelligence overview")
    intel_overview.add_argument("--project-id")

    # Agents (Phase 11)
    agents = sub.add_parser("agents", help="AI Agent Evaluation, Trajectory Testing & Reliability")
    agents_sub = agents.add_subparsers(dest="agents_command", required=True)

    ag_create = agents_sub.add_parser("create", help="create a new agent definition")
    ag_create.add_argument("--name", required=True, help="agent name")
    ag_create.add_argument("--description", help="agent description")
    ag_create.add_argument("--agent-type", default="TOOL_AGENT", help="CHAT_AGENT, TOOL_AGENT, RAG_AGENT, etc.")
    ag_create.add_argument("--prompt", help="system prompt")
    ag_create.add_argument("--project-id")

    ag_list = agents_sub.add_parser("list", help="list agents in project")
    ag_list.add_argument("--project-id")

    ag_run = agents_sub.add_parser("run", help="start an agent execution run")
    ag_run.add_argument("--agent-id", required=True, help="agent definition UUID")
    ag_run.add_argument("--env-id", help="optional environment UUID")
    ag_run.add_argument("--task", help="task JSON or instruction prompt")
    ag_run.add_argument("--project-id")

    ag_status = agents_sub.add_parser("status", help="get status of an agent run")
    ag_status.add_argument("--run-id", required=True, help="agent run UUID")
    ag_status.add_argument("--project-id")

    ag_traj = agents_sub.add_parser("trajectory", help="get step-by-step trajectory of an agent run")
    ag_traj.add_argument("--run-id", required=True, help="agent run UUID")
    ag_traj.add_argument("--project-id")

    ag_eval = agents_sub.add_parser("evaluate", help="evaluate trajectory and compute reliability score")
    ag_eval.add_argument("--run-id", required=True, help="agent run UUID")
    ag_eval.add_argument("--project-id")

    ag_bench = agents_sub.add_parser("benchmark", help="run or view agent benchmark evaluations")
    ag_bench.add_argument("--agent-id", required=True, help="agent definition UUID")
    ag_bench.add_argument("--project-id")

    # System (Phase 12)
    system_parser = sub.add_parser("system", help="Production deployment, readiness diagnostics & maintenance")
    system_sub = system_parser.add_subparsers(dest="system_command", required=True)

    sys_status = system_sub.add_parser("status", help="quick system status check")
    sys_status.add_argument("--json", action="store_true", help="output json")

    sys_readiness = system_sub.add_parser("readiness", help="full structured deployment readiness diagnostics")
    sys_readiness.add_argument("--json", action="store_true", help="output json")

    sys_ver = system_sub.add_parser("version", help="show version and database schema migration compatibility")
    sys_ver.add_argument("--json", action="store_true", help="output json")

    sys_workers = system_sub.add_parser("workers", help="check active background worker heartbeats")
    sys_workers.add_argument("--json", action="store_true", help="output json")

    sys_backup = system_sub.add_parser("backup", help="create a verified database backup with checksum")
    sys_backup.add_argument("--output", help="custom output path for backup file")
    sys_backup.add_argument("--json", action="store_true", help="output json")

    sys_verify = system_sub.add_parser("verify-backup", help="verify backup file integrity and checksum")
    sys_verify.add_argument("path", help="path to backup dump file")
    sys_verify.add_argument("--json", action="store_true", help="output json")

    # Enterprise (Phase 13)
    ent_parser = sub.add_parser("enterprise", help="Enterprise identity, collaboration & governance")
    ent_parser.add_argument("--org-id", help="Target organization UUID")
    ent_sub = ent_parser.add_subparsers(dest="enterprise_command", required=True)

    # identity
    ent_id = ent_sub.add_parser("identity", help="manage identity providers")
    ent_id_sub = ent_id.add_subparsers(dest="identity_action", required=True)
    ent_id_sub.add_parser("list")
    ent_id_create = ent_id_sub.add_parser("create")
    ent_id_create.add_argument("--name", required=True)
    ent_id_create.add_argument("--provider-type", default="OIDC")
    ent_id_create.add_argument("--client-id")
    ent_id_create.add_argument("--client-secret")
    ent_id_enable = ent_id_sub.add_parser("enable")
    ent_id_enable.add_argument("idp_id")
    ent_id_disable = ent_id_sub.add_parser("disable")
    ent_id_disable.add_argument("idp_id")

    # domains
    ent_dom = ent_sub.add_parser("domains", help="manage organization domains")
    ent_dom_sub = ent_dom.add_subparsers(dest="domain_action", required=True)
    ent_dom_sub.add_parser("list")
    ent_dom_verify = ent_dom_sub.add_parser("verify")
    ent_dom_verify.add_argument("domain_id")

    # teams
    ent_team = ent_sub.add_parser("teams", help="manage teams and membership")
    ent_team_sub = ent_team.add_subparsers(dest="team_action", required=True)
    ent_team_sub.add_parser("list")
    ent_team_create = ent_team_sub.add_parser("create")
    ent_team_create.add_argument("--name", required=True)
    ent_team_create.add_argument("--description")
    ent_team_members = ent_team_sub.add_parser("members")
    ent_team_members.add_argument("team_id")

    # tokens
    ent_tok = ent_sub.add_parser("tokens", help="manage service tokens")
    ent_tok_sub = ent_tok.add_subparsers(dest="token_action", required=True)
    ent_tok_sub.add_parser("list")
    ent_tok_revoke = ent_tok_sub.add_parser("revoke")
    ent_tok_revoke.add_argument("token_id")

    # policies
    ent_pol = ent_sub.add_parser("policies", help="manage governance policies")
    ent_pol_sub = ent_pol.add_subparsers(dest="policy_action", required=True)
    ent_pol_sub.add_parser("list")
    ent_pol_create = ent_pol_sub.add_parser("create")
    ent_pol_create.add_argument("--name", required=True)
    ent_pol_create.add_argument("--description")
    ent_pol_act = ent_pol_sub.add_parser("activate")
    ent_pol_act.add_argument("policy_id")

    # approvals
    ent_app = ent_sub.add_parser("approvals", help="manage approval workflows")
    ent_app_sub = ent_app.add_subparsers(dest="approval_action", required=True)
    ent_app_sub.add_parser("list")
    ent_app_approve = ent_app_sub.add_parser("approve")
    ent_app_approve.add_argument("request_id")
    ent_app_approve.add_argument("--comments")
    ent_app_reject = ent_app_sub.add_parser("reject")
    ent_app_reject.add_argument("request_id")
    ent_app_reject.add_argument("--comments")

    # access-review
    ent_rev = ent_sub.add_parser("access-review", help="manage access review campaigns")
    ent_rev_sub = ent_rev.add_subparsers(dest="review_action", required=True)
    ent_rev_sub.add_parser("list")
    ent_rev_create = ent_rev_sub.add_parser("create")
    ent_rev_create.add_argument("--title", required=True)
    ent_rev_comp = ent_rev_sub.add_parser("complete")
    ent_rev_comp.add_argument("review_id")

    # Compliance (Phase 14)
    comp_parser = sub.add_parser("compliance", help="Compliance, audit intelligence & data governance")
    comp_parser.add_argument("--org-id", help="Target organization UUID")
    comp_sub = comp_parser.add_subparsers(dest="compliance_command", required=True)

    # framework
    comp_fw = comp_sub.add_parser("framework", help="manage compliance frameworks")
    comp_fw_sub = comp_fw.add_subparsers(dest="framework_action", required=True)
    comp_fw_sub.add_parser("list")
    comp_fw_create = comp_fw_sub.add_parser("create")
    comp_fw_create.add_argument("--name", required=True)
    comp_fw_create.add_argument("--description")
    comp_fw_act = comp_fw_sub.add_parser("activate")
    comp_fw_act.add_argument("framework_id")

    # control
    comp_ctrl = comp_sub.add_parser("control", help="manage compliance controls")
    comp_ctrl_sub = comp_ctrl.add_subparsers(dest="control_action", required=True)
    comp_ctrl_list = comp_ctrl_sub.add_parser("list")
    comp_ctrl_list.add_argument("framework_id")
    comp_ctrl_create = comp_ctrl_sub.add_parser("create")
    comp_ctrl_create.add_argument("framework_id")
    comp_ctrl_create.add_argument("--control-id", required=True)
    comp_ctrl_create.add_argument("--title", required=True)
    comp_ctrl_create.add_argument("--category", default="GOVERNANCE")
    comp_ctrl_create.add_argument("--risk-level", default="MEDIUM")
    comp_ctrl_create.add_argument("--description")

    # evidence
    comp_ev = comp_sub.add_parser("evidence", help="manage compliance evidence registry")
    comp_ev_sub = comp_ev.add_subparsers(dest="evidence_action", required=True)
    comp_ev_sub.add_parser("list")
    comp_ev_rec = comp_ev_sub.add_parser("record")
    comp_ev_rec.add_argument("--source-type", required=True)
    comp_ev_rec.add_argument("--source-id", required=True)
    comp_ev_rec.add_argument("--project-id")
    comp_ev_ver = comp_ev_sub.add_parser("verify")
    comp_ev_ver.add_argument("evidence_id")

    # assessment
    comp_ass = comp_sub.add_parser("assessment", help="manage compliance assessments")
    comp_ass_sub = comp_ass.add_subparsers(dest="assessment_action", required=True)
    comp_ass_sub.add_parser("list")
    comp_ass_create = comp_ass_sub.add_parser("create")
    comp_ass_create.add_argument("--framework-id", required=True)
    comp_ass_create.add_argument("--title", required=True)
    comp_ass_run = comp_ass_sub.add_parser("run")
    comp_ass_run.add_argument("assessment_id")
    comp_ass_app = comp_ass_sub.add_parser("approve")
    comp_ass_app.add_argument("assessment_id")
    comp_ass_app.add_argument("--comment")
    comp_ass_rej = comp_ass_sub.add_parser("reject")
    comp_ass_rej.add_argument("assessment_id")
    comp_ass_rej.add_argument("--comment")

    # remediation
    comp_rem = comp_sub.add_parser("remediation", help="manage remediations and risk acceptance")
    comp_rem_sub = comp_rem.add_subparsers(dest="remediation_action", required=True)
    comp_rem_sub.add_parser("list")
    comp_rem_create = comp_rem_sub.add_parser("create")
    comp_rem_create.add_argument("--control-id", required=True)
    comp_rem_create.add_argument("--title", required=True)
    comp_rem_create.add_argument("--severity", default="MEDIUM")
    comp_rem_create.add_argument("--description")
    comp_rem_res = comp_rem_sub.add_parser("resolve")
    comp_rem_res.add_argument("remediation_id")
    comp_rem_res.add_argument("--notes", required=True)
    comp_rem_acc = comp_rem_sub.add_parser("accept-risk")
    comp_rem_acc.add_argument("remediation_id")
    comp_rem_acc.add_argument("--justification", required=True)

    # retention
    comp_ret = comp_sub.add_parser("retention", help="manage retention policies and cleanup")
    comp_ret_sub = comp_ret.add_subparsers(dest="retention_action", required=True)
    comp_ret_sub.add_parser("list")
    comp_ret_create = comp_ret_sub.add_parser("create")
    comp_ret_create.add_argument("--resource-type", required=True)
    comp_ret_create.add_argument("--days", type=int, required=True)
    comp_ret_create.add_argument("--description")
    comp_ret_clean = comp_ret_sub.add_parser("cleanup")
    comp_ret_clean.add_argument("--dry-run", action="store_true", default=True)

    # legal-hold
    comp_hold = comp_sub.add_parser("legal-hold", help="manage legal preservation holds")
    comp_hold_sub = comp_hold.add_subparsers(dest="hold_action", required=True)
    comp_hold_sub.add_parser("list")
    comp_hold_create = comp_hold_sub.add_parser("create")
    comp_hold_create.add_argument("--title", required=True)
    comp_hold_create.add_argument("--resource-type", required=True)
    comp_hold_create.add_argument("--target-id", required=True)
    comp_hold_create.add_argument("--reason")
    comp_hold_rel = comp_hold_sub.add_parser("release")
    comp_hold_rel.add_argument("hold_id")

    # audit
    comp_aud = comp_sub.add_parser("audit", help="query unified audit intelligence timeline")
    comp_aud_sub = comp_aud.add_subparsers(dest="audit_action", required=True)
    comp_aud_list = comp_aud_sub.add_parser("list")
    comp_aud_list.add_argument("--category")
    comp_aud_list.add_argument("--limit", type=int, default=50)

    # report
    comp_rep = comp_sub.add_parser("report", help="export compliance report")
    comp_rep_sub = comp_rep.add_subparsers(dest="report_action", required=True)
    comp_rep_exp = comp_rep_sub.add_parser("export")
    comp_rep_exp.add_argument("assessment_id")
    comp_rep_exp.add_argument("--format", choices=["json", "csv"], default="json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    cmd = args.command
    if cmd == "version":
        return cmd_version(args)
    if cmd == "health":
        return cmd_health(args)
    if cmd == "init":
        return cmd_init(args)

    if cmd == "auth":
        if args.auth_command == "login":
            return cmd_login(args)
        if args.auth_command == "logout":
            return cmd_logout(args)
        if args.auth_command == "status":
            return cmd_auth_status(args)

    if cmd == "projects":
        if args.projects_command == "list":
            return cmd_project_list(args)
        if args.projects_command == "current":
            return cmd_project_current(args)

    if cmd == "datasets":
        if args.datasets_command == "list":
            return cmd_dataset_list(args)
        if args.datasets_command == "validate":
            return cmd_dataset_validate(args)

    if cmd == "experiments":
        if args.experiments_command == "create":
            return cmd_experiment_create(args)
        if args.experiments_command == "run":
            return cmd_experiment_run(args)
        if args.experiments_command == "status":
            return cmd_experiment_status(args)
        if args.experiments_command == "results":
            return cmd_experiment_results(args)
        if args.experiments_command == "cancel":
            return cmd_experiment_cancel(args)

    if cmd == "evaluations":
        if args.evaluations_command == "run":
            return cmd_evaluations_run(args)
        if args.evaluations_command == "results":
            return cmd_evaluations_results(args)

    if cmd == "benchmarks":
        if args.benchmarks_command == "create":
            return cmd_benchmark_create(args)
        if args.benchmarks_command == "run":
            return cmd_benchmark_run(args)
        if args.benchmarks_command == "status":
            return cmd_benchmark_status(args)
        if args.benchmarks_command == "results":
            return cmd_benchmark_results(args)
        if args.benchmarks_command == "reproduce":
            return cmd_benchmark_reproduce(args)

    if cmd == "quality-gate" and args.gate_command == "check":
        return cmd_quality_gate_check(args)

    if cmd == "decision":
        if args.decision_command == "create":
            return cmd_decision_create(args)
        if args.decision_command == "evaluate":
            return cmd_decision_evaluate(args)
        if args.decision_command == "status":
            return cmd_decision_status(args)
        if args.decision_command == "evidence":
            return cmd_decision_evidence(args)
        if args.decision_command == "checks":
            return cmd_decision_checks(args)
        if args.decision_command == "compare":
            return cmd_decision_compare(args)

    if cmd == "intelligence":
        if args.intelligence_command == "overview":
            return cmd_intelligence_overview(args)

    if cmd == "agents":
        if args.agents_command == "create":
            return cmd_agents_create(args)
        if args.agents_command == "list":
            return cmd_agents_list(args)
        if args.agents_command == "run":
            return cmd_agents_run(args)
        if args.agents_command == "status":
            return cmd_agents_status(args)
        if args.agents_command == "trajectory":
            return cmd_agents_trajectory(args)
        if args.agents_command == "evaluate":
            return cmd_agents_evaluate(args)
        if args.agents_command == "benchmark":
            return cmd_agents_benchmark(args)

    if cmd == "system":
        if args.system_command == "status":
            return cmd_system_status(args)
        if args.system_command == "readiness":
            return cmd_system_readiness(args)
        if args.system_command == "version":
            return cmd_system_version(args)
        if args.system_command == "workers":
            return cmd_system_workers(args)
        if args.system_command == "backup":
            return cmd_system_backup(args)
        if args.system_command == "verify-backup":
            return cmd_system_verify_backup(args)

    if cmd == "enterprise":
        c = args.enterprise_command
        if c == "identity":
            act = args.identity_action
            if act == "list": return cmd_enterprise_identity_list(args)
            if act == "create": return cmd_enterprise_identity_create(args)
            if act == "enable": return cmd_enterprise_identity_enable(args)
            if act == "disable": return cmd_enterprise_identity_disable(args)
        if c == "domains":
            act = args.domain_action
            if act == "list": return cmd_enterprise_domains_list(args)
            if act == "verify": return cmd_enterprise_domains_verify(args)
        if c == "teams":
            act = args.team_action
            if act == "list": return cmd_enterprise_teams_list(args)
            if act == "create": return cmd_enterprise_teams_create(args)
            if act == "members": return cmd_enterprise_teams_members(args)
        if c == "tokens":
            act = args.token_action
            if act == "list": return cmd_enterprise_tokens_list(args)
            if act == "revoke": return cmd_enterprise_tokens_revoke(args)
        if c == "policies":
            act = args.policy_action
            if act == "list": return cmd_enterprise_policies_list(args)
            if act == "create": return cmd_enterprise_policies_create(args)
            if act == "activate": return cmd_enterprise_policies_activate(args)
        if c == "approvals":
            act = args.approval_action
            if act == "list": return cmd_enterprise_approvals_list(args)
            if act == "approve": return cmd_enterprise_approvals_approve(args)
            if act == "reject": return cmd_enterprise_approvals_reject(args)
        if c == "access-review":
            act = args.review_action
            if act == "list": return cmd_enterprise_access_review_list(args)
            if act == "create": return cmd_enterprise_access_review_create(args)
            if act == "complete": return cmd_enterprise_access_review_complete(args)

    if cmd == "compliance":
        c = args.compliance_command
        if c == "framework":
            act = args.framework_action
            if act == "list": return cmd_compliance_framework_list(args)
            if act == "create": return cmd_compliance_framework_create(args)
            if act == "activate": return cmd_compliance_framework_activate(args)
        if c == "control":
            act = args.control_action
            if act == "list": return cmd_compliance_control_list(args)
            if act == "create": return cmd_compliance_control_create(args)
        if c == "evidence":
            act = args.evidence_action
            if act == "list": return cmd_compliance_evidence_list(args)
            if act == "record": return cmd_compliance_evidence_record(args)
            if act == "verify": return cmd_compliance_evidence_verify(args)
        if c == "assessment":
            act = args.assessment_action
            if act == "list": return cmd_compliance_assessment_list(args)
            if act == "create": return cmd_compliance_assessment_create(args)
            if act == "run": return cmd_compliance_assessment_run(args)
            if act == "approve": return cmd_compliance_assessment_approve(args)
            if act == "reject": return cmd_compliance_assessment_reject(args)
        if c == "remediation":
            act = args.remediation_action
            if act == "list": return cmd_compliance_remediation_list(args)
            if act == "create": return cmd_compliance_remediation_create(args)
            if act == "resolve": return cmd_compliance_remediation_resolve(args)
            if act == "accept-risk": return cmd_compliance_remediation_accept_risk(args)
        if c == "retention":
            act = args.retention_action
            if act == "list": return cmd_compliance_retention_list(args)
            if act == "create": return cmd_compliance_retention_create(args)
            if act == "cleanup": return cmd_compliance_retention_cleanup(args)
        if c == "legal-hold":
            act = args.hold_action
            if act == "list": return cmd_compliance_legal_hold_list(args)
            if act == "create": return cmd_compliance_legal_hold_create(args)
            if act == "release": return cmd_compliance_legal_hold_release(args)
        if c == "audit":
            act = args.audit_action
            if act == "list": return cmd_compliance_audit_list(args)
        if c == "report":
            act = args.report_action
            if act == "export": return cmd_compliance_report_export(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
