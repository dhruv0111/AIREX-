# Run Alembic migrations in the API container (PowerShell)
docker compose exec -T api alembic upgrade head
