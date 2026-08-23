# ============================================================
# AIREX — Makefile (Phase 0)
# Windows developers: use scripts/setup.ps1 or scripts/*.ps1
# ============================================================

SHELL := /bin/bash
.PHONY: setup dev stop logs migrate migration seed test lint format typecheck e2e clean build

# ---- Setup / lifecycle ----
setup:
	@echo "==> Copying environment template"
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@echo "==> Building and starting Docker stack"
	docker compose up -d --build
	@echo "==> Running migrations"
	$(MAKE) migrate
	@echo "==> Done. Web: http://localhost:3000  API: http://localhost:8000/docs"

dev:
	docker compose up -d

stop:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf data .pytest_cache .mypy_cache .ruff_cache node_modules .next

# ---- Database ----
migrate:
	docker compose exec api alembic upgrade head

migration:
	docker compose exec api alembic revision --autogenerate -m "$(name)"

seed:
	docker compose exec api python -m app.seed

# ---- Tests ----
test:
	docker compose exec api pytest -q

lint:
	docker compose exec api ruff check app tests
	cd apps/web && npx eslint . --max-warnings 0

format:
	docker compose exec api black app tests
	cd apps/web && npx prettier --write .

typecheck:
	docker compose exec api mypy app
	cd apps/web && npx tsc --noEmit

e2e:
	npx playwright test

# ---- Build ----
build:
	docker compose build
