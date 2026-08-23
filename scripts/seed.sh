#!/usr/bin/env bash
set -euo pipefail
docker compose exec -T api python -m app.seed
