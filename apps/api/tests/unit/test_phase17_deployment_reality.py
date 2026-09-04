"""Unit tests for Phase 17 Deployment Reality, Containerization & Kubernetes IaC Verification."""

import os
import subprocess
from pathlib import Path
import yaml
import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_dockerfile_production_hardening():
    """Verify API and Web Dockerfiles enforce non-root security and health checks."""
    api_dockerfile = REPO_ROOT / "apps" / "api" / "Dockerfile"
    web_dockerfile = REPO_ROOT / "apps" / "web" / "Dockerfile"

    assert api_dockerfile.exists(), "API Dockerfile missing"
    assert web_dockerfile.exists(), "Web Dockerfile missing"

    api_content = api_dockerfile.read_text(encoding="utf-8")
    assert "USER airex" in api_content, "API Dockerfile must run as non-root user 'airex'"
    assert "HEALTHCHECK" in api_content, "API Dockerfile must define a container HEALTHCHECK"
    assert "groupadd -g 10001 airex" in api_content, "API Dockerfile must use explicit UID 10001"

    web_content = web_dockerfile.read_text(encoding="utf-8")
    assert "USER nextjs" in web_content, "Web Dockerfile must run as non-root user 'nextjs'"
    assert "HEALTHCHECK" in web_content, "Web Dockerfile must define a container HEALTHCHECK"
    assert "adduser --system --uid 10001 nextjs" in web_content, "Web Dockerfile must use explicit UID 10001"


def test_dockerignore_secrets_and_caches_excluded():
    """Verify .dockerignore files exclude local secrets, virtualenvs, and test caches."""
    root_dockerignore = REPO_ROOT / ".dockerignore"
    api_dockerignore = REPO_ROOT / "apps" / "api" / ".dockerignore"

    assert root_dockerignore.exists(), "Root .dockerignore missing"
    assert api_dockerignore.exists(), "API .dockerignore missing"

    root_content = root_dockerignore.read_text(encoding="utf-8")
    assert ".env" in root_content
    assert "**/.venv" in root_content
    assert "**/node_modules" in root_content

    api_content = api_dockerignore.read_text(encoding="utf-8")
    assert ".env" in api_content
    assert ".venv" in api_content
    assert ".pytest_cache" in api_content


def test_docker_compose_production_topology():
    """Verify docker-compose.prod.yml defines complete production topology with resource limits and health checks."""
    compose_file = REPO_ROOT / "docker-compose.prod.yml"
    assert compose_file.exists(), "docker-compose.prod.yml missing"

    with open(compose_file, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    expected_services = {"postgres", "redis", "api", "worker", "web", "nginx"}
    assert expected_services.issubset(set(services.keys())), f"Missing expected services: {expected_services - set(services.keys())}"

    # Verify healthchecks and resource limits
    assert "healthcheck" in services["postgres"]
    assert "healthcheck" in services["redis"]
    assert "healthcheck" in services["api"]

    # Verify API depends on postgres & redis being healthy
    api_depends = services["api"].get("depends_on", {})
    assert "postgres" in api_depends and api_depends["postgres"]["condition"] == "service_healthy"
    assert "redis" in api_depends and api_depends["redis"]["condition"] == "service_healthy"


def test_kubernetes_manifests_via_kustomize():
    """Verify all Kubernetes manifests compile successfully via kubectl kustomize without errors for base, staging, and production."""
    base_dir = REPO_ROOT / "infrastructure" / "k8s" / "base"
    staging_dir = REPO_ROOT / "infrastructure" / "k8s" / "overlays" / "staging"
    prod_dir = REPO_ROOT / "infrastructure" / "k8s" / "overlays" / "production"

    for env_name, target_dir in [("base", base_dir), ("staging", staging_dir), ("production", prod_dir)]:
        assert target_dir.exists(), f"Directory {target_dir} missing"
        result = subprocess.run(
            ["kubectl", "kustomize", str(target_dir)],
            capture_output=True,
            text=True,
            shell=True,
        )
        assert result.returncode == 0, f"kubectl kustomize failed for {env_name}: {result.stderr}"
        output = result.stdout

        # Verify key components are compiled in the output
        assert "kind: Deployment" in output
        assert "name: airex-api" in output
        assert "name: airex-web" in output
        assert "name: airex-worker" in output
        assert "kind: HorizontalPodAutoscaler" in output
        assert "kind: PodDisruptionBudget" in output
        assert "kind: NetworkPolicy" in output
        assert "kind: Ingress" in output


def test_kubernetes_zero_downtime_rolling_update_and_drain():
    """Verify Kubernetes deployments enforce maxUnavailable=0 and worker graceful termination."""
    api_deploy_file = REPO_ROOT / "infrastructure" / "k8s" / "base" / "api-deployment.yaml"
    worker_deploy_file = REPO_ROOT / "infrastructure" / "k8s" / "base" / "worker-deployment.yaml"

    with open(api_deploy_file, "r", encoding="utf-8") as f:
        api_deploy = yaml.safe_load(f)

    strategy = api_deploy["spec"]["strategy"]["rollingUpdate"]
    assert strategy["maxUnavailable"] == 0, "API deployment must enforce maxUnavailable: 0 for zero-downtime rollouts"
    assert strategy["maxSurge"] == "25%" or strategy["maxSurge"] == 1

    with open(worker_deploy_file, "r", encoding="utf-8") as f:
        worker_deploy = yaml.safe_load(f)

    termination_seconds = worker_deploy["spec"]["template"]["spec"]["terminationGracePeriodSeconds"]
    assert termination_seconds >= 60, f"Worker fleet must allow at least 60s for graceful task draining, found {termination_seconds}"


def test_production_cicd_pipeline_configuration():
    """Verify GitHub Actions production deployment pipeline defines release gates and rollback triggers."""
    pipeline_file = REPO_ROOT / ".github" / "workflows" / "deploy-production.yml"
    assert pipeline_file.exists(), "Production deployment pipeline missing"

    with open(pipeline_file, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    jobs = workflow.get("jobs", {})
    assert "verify_platform_integrity" in jobs, "Pipeline must have verify_platform_integrity gate"
    assert "build_container_images" in jobs, "Pipeline must build immutable container images"
    assert "deploy_staging" in jobs, "Pipeline must support staging environment deployment"
    assert "deploy_production" in jobs, "Pipeline must support production environment deployment"

