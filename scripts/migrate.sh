#!/usr/bin/env bash
set -euo pipefail
docker compose exec -T api alembic upgrade head
