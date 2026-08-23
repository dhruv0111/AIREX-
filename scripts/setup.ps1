# AIREX setup (PowerShell)
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from template"
    Copy-Item ".env.example" ".env"
}

Write-Host "==> Starting Docker stack"
docker compose up -d --build

Write-Host "==> Waiting for API to become ready"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { throw "API did not become ready in time." }

Write-Host "==> Running migrations"
docker compose exec -T api alembic upgrade head

Write-Host "==> Seeding demo data"
docker compose exec -T api python -m app.seed

Write-Host "==> Done. Web: http://localhost:3000  API docs: http://localhost:8000/docs"
