# AIREX API — hardened production-ready image (spec §46, §62; AT-021; Phase 12)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 airex \
    && useradd -u 10001 -g airex -s /bin/bash -m airex

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN pip install --upgrade pip \
    && pip install . \
    && mkdir -p /app/data /app/backups \
    && chown -R airex:airex /app

USER airex

EXPOSE 8000

# Healthcheck hits /health/live
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
