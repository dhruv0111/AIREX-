#!/usr/bin/env bash
# AIREX setup (bash). Windows: use scripts/setup.ps1
set -euo pipefail

if [ ! -f .env ]; then
  echo "==> Creating .env from template"
  cp .env.example .env
fi

echo "==> Starting Docker stack"
docker compose up -d --build

echo "==> Waiting for API to become ready"
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/health > /dev/null; then
    break
  fi
  sleep 2
done

echo "==> Running migrations"
docker compose exec -T api alembic upgrade head

echo "==> Seeding demo data"
docker compose exec -T api python -m app.seed

echo "==> Done. Web: http://localhost:3000  API docs: http://localhost:8000/docs"
