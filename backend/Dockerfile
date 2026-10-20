# syntax=docker/dockerfile:1
# Base image registry prefix: Docker Hub is often unreachable from Iran; e.g. REGISTRY=docker.arvancloud.ir/
ARG REGISTRY=
FROM ${REGISTRY}python:3.12-slim

# Optional PyPI mirror (e.g. https://package-mirror.liara.ir/repository/pypi/simple or https://mirror-pypi.runflare.com/simple)
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DEFAULT_TIMEOUT=120 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app/backend

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY database /app/database

RUN useradd --create-home --uid 10001 app && mkdir -p /data/files && chown -R app /data/files /app
USER app

EXPOSE 8000
# Migrations: RUN_MIGRATIONS_ON_STARTUP=true applies database/migrations/*.sql once each (tracked in applied_migration_files).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
