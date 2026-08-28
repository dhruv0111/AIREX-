"""GitHub and GitLab live integration smoke test runner.

Runs against the live Docker E2E stack (localhost:8010).
"""
import asyncio
import httpx
import os
import subprocess
import yaml

API_URL = os.environ.get("E2E_API_URL") or "http://localhost:8000"
EMAIL = "demo@example.com"
PASSWORD = "demo-password-123"

async def main():
    print("--- Starting CI Live Smoke Tests ---")
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
        # 1. Login
        print("Logging in...")
        login_resp = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        access_token = login_resp.json()["data"]["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        # 2. Get organization and project ID
        print("Fetching user organization...")
        orgs_resp = await client.get("/api/v1/organizations", headers=headers)
        assert orgs_resp.status_code == 200
        org_id = orgs_resp.json()["data"][0]["id"]
        headers["X-Organization-Id"] = org_id

        print("Fetching project...")
        projects_resp = await client.get("/api/v1/projects", headers=headers)
        assert projects_resp.status_code == 200
        project = projects_resp.json()["data"][0]
        project_id = project["id"]
        project_slug = project["slug"]
        print(f"Project ID: {project_id}, Slug: {project_slug}")

        # 3. Create or reuse LOCAL provider
        print("Checking providers...")
        prov_list_resp = await client.get("/api/v1/providers", headers=headers)
        assert prov_list_resp.status_code == 200
        existing_prov = [p for p in prov_list_resp.json()["data"] if p["name"] == "Smoke Provider"]
        
        if existing_prov:
            provider_id = existing_prov[0]["id"]
            print(f"Reusing existing provider: {provider_id}")
        else:
            print("Creating local provider...")
            prov_resp = await client.post("/api/v1/providers", headers=headers, json={
                "provider_type": "LOCAL",
                "name": "Smoke Provider",
            })
            assert prov_resp.status_code in (200, 201), f"Provider creation failed: {prov_resp.text}"
            provider_id = prov_resp.json()["data"]["id"]

        # 4. Create or reuse models
        print("Checking models...")
        models_list_resp = await client.get(f"/api/v1/projects/{project_id}/models", headers=headers)
        assert models_list_resp.status_code == 200
        existing_models = {m["model_identifier"]: m for m in models_list_resp.json()["data"]}

        if "gpt-4o" in existing_models:
            print("Reusing existing model: gpt-4o")
        else:
            print("Creating baseline model gpt-4o...")
            m1_resp = await client.post(f"/api/v1/projects/{project_id}/models", headers=headers, json={
                "name": "gpt-4o",
                "model_identifier": "gpt-4o",
                "provider_id": provider_id,
                "configuration": {},
            })
            assert m1_resp.status_code in (200, 201), f"Model 1 creation failed: {m1_resp.text}"

        if "claude-3-5" in existing_models:
            print("Reusing existing model: claude-3-5")
        else:
            print("Creating candidate model claude-3-5...")
            m2_resp = await client.post(f"/api/v1/projects/{project_id}/models", headers=headers, json={
                "name": "claude-3-5",
                "model_identifier": "claude-3-5",
                "provider_id": provider_id,
                "configuration": {},
            })
            assert m2_resp.status_code in (200, 201), f"Model 2 creation failed: {m2_resp.text}"

        # 5. Create or reuse dataset
        print("Checking datasets...")
        ds_list_resp = await client.get(f"/api/v1/projects/{project_id}/datasets", headers=headers)
        assert ds_list_resp.status_code == 200
        existing_ds = [d for d in ds_list_resp.json()["data"] if d["name"] == "production-dataset"]

        if existing_ds:
            dataset_id = existing_ds[0]["id"]
            print(f"Reusing existing dataset: {dataset_id}")
        else:
            print("Creating dataset...")
            ds_resp = await client.post(f"/api/v1/projects/{project_id}/datasets", headers=headers, json={
                "name": "production-dataset",
            })
            assert ds_resp.status_code in (200, 201), f"Dataset creation failed: {ds_resp.text}"
            dataset_id = ds_resp.json()["data"]["id"]

            print("Uploading dataset version...")
            file_content = '{"input": "Hi", "expected_output": "[local:claude-3-5] Hi"}\n' * 5
            boundary = "------SmokeBoundary"
            multipart_data = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="cases.jsonl"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n"
                f"{file_content}\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="format"\r\n\r\n'
                f"jsonl\r\n"
                f"--{boundary}--\r\n"
            )
            dsv_resp = await client.post(
                f"/api/v1/datasets/{dataset_id}/versions",
                headers={**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
                content=multipart_data
            )
            assert dsv_resp.status_code in (200, 201), f"Dataset version upload failed: {dsv_resp.text}"

        # 6. Generate Service Token
        print("Generating service token...")
        tok_resp = await client.post(f"/api/v1/projects/{project_id}/service-tokens", headers=headers, json={
            "name": "CI Smoke Token",
            "scopes": ["experiments:run", "experiments:read"],
            "expires_in_days": 30,
        })
        assert tok_resp.status_code == 201, f"Token creation failed: {tok_resp.text}"
        raw_token = tok_resp.json()["data"]["raw_token"]
        print(f"Service token generated successfully.")

    # 7. Write temporary airex.yaml
    yaml_config = {
        "version": "1",
        "project": str(project_id),
        "experiment": {
            "dataset": "production-dataset",
            "baseline": {"model": "gpt-4o"},
            "candidate": {"model": "claude-3-5"},
        },
        "quality_gates": [
            {"metric": "exact_match", "operator": "gte", "threshold": 0.90, "required": True}
        ]
    }
    with open("airex.yaml", "w") as f:
        yaml.safe_dump(yaml_config, f)
    print("Wrote temporary configuration to airex.yaml")

    # 8. Execute GitHub actions simulated run
    print("\n--- Running GitHub Actions Live Smoke Test ---")
    gh_env = os.environ.copy()
    gh_env["AIREX_API_URL"] = API_URL
    gh_env["AIREX_API_TOKEN"] = raw_token
    gh_env["AIREX_PROJECT_ID"] = str(project_id)
    gh_env["GITHUB_ACTIONS"] = "true"
    gh_env["GITHUB_RUN_ID"] = "gh_run_smoke_123"
    gh_env["GITHUB_JOB"] = "gh_job_smoke"
    gh_env["GITHUB_SHA"] = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    gh_env["GITHUB_REF_NAME"] = "main"
    gh_env["GITHUB_REPOSITORY"] = "test-org/test-repo"

    res_gh = subprocess.run(
        ["python", "-m", "app.cli", "experiments", "run", "--config", "airex.yaml", "--poll-interval", "2.0"],
        env=gh_env,
        capture_output=True,
        text=True
    )
    print("GitHub CLI Output:")
    print(res_gh.stdout)
    if res_gh.stderr:
        print("GitHub CLI Error:")
        print(res_gh.stderr)
    assert res_gh.returncode == 0, f"GitHub Actions run failed with returncode {res_gh.returncode}"

    # 9. Execute GitLab CI simulated run
    print("\n--- Running GitLab CI Live Smoke Test ---")
    gl_env = os.environ.copy()
    gl_env["AIREX_API_URL"] = API_URL
    gl_env["AIREX_API_TOKEN"] = raw_token
    gl_env["AIREX_PROJECT_ID"] = str(project_id)
    gl_env["GITLAB_CI"] = "true"
    gl_env["CI_PIPELINE_ID"] = "gl_run_smoke_456"
    gl_env["CI_JOB_ID"] = "gl_job_smoke"
    gl_env["CI_COMMIT_SHA"] = "f6e5d4c3b2a1f6e5d4c3b2a1f6e5d4c3b2a1f6e5"
    gl_env["CI_COMMIT_BRANCH"] = "main"
    gl_env["CI_PROJECT_PATH"] = "test-org/test-gitlab-repo"

    res_gl = subprocess.run(
        ["python", "-m", "app.cli", "experiments", "run", "--config", "airex.yaml", "--poll-interval", "2.0"],
        env=gl_env,
        capture_output=True,
        text=True
    )
    print("GitLab CLI Output:")
    print(res_gl.stdout)
    if res_gl.stderr:
        print("GitLab CLI Error:")
        print(res_gl.stderr)
    assert res_gl.returncode == 0, f"GitLab CI run failed with returncode {res_gl.returncode}"

    # 10. Clean up
    if os.path.exists("airex.yaml"):
        os.remove("airex.yaml")
    print("Removed temporary airex.yaml")

    # 11. Verify runs are recorded on the server
    async with httpx.AsyncClient(base_url=API_URL, timeout=10) as client:
        runs_resp = await client.get(f"/api/v1/projects/{project_id}/ci-runs", headers=headers)
        assert runs_resp.status_code == 200
        runs = runs_resp.json()["data"]
        print(f"\nVerification: Found {len(runs)} CI runs on server:")
        for r in runs:
            print(f"- Run ID: {r['id']}, CI Provider: {r['ci_provider']}, Commit: {r['commit_sha']}, Status: {r['status']}")
        
        assert any(r["ci_provider"] == "GITHUB_ACTIONS" for r in runs), "GitHub Actions run missing on server"
        assert any(r["ci_provider"] == "GITLAB_CI" for r in runs), "GitLab CI run missing on server"
        print("\n--- ALL CI LIVE SMOKE TESTS PASSED ---")

if __name__ == "__main__":
    asyncio.run(main())
