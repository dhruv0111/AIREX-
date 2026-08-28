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

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
