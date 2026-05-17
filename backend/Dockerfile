# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VERSION=2.4.1
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install "poetry==${POETRY_VERSION}"
WORKDIR /app

FROM base AS deps
COPY backend/pyproject.toml backend/poetry.lock ./
RUN poetry install --only main --no-root

FROM deps AS runtime
COPY backend/src ./src
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
