#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# sed -i differs between GNU (no arg) and BSD/macOS (empty-string arg).
# Detect once and use the right form everywhere below.
if sed --version >/dev/null 2>&1; then
  sed_i() { sed -i "$@"; }
else
  sed_i() { sed -i '' "$@"; }
fi

if [[ ! -f .env ]]; then
  echo "→ Generating .env from .env.example"
  cp .env.example .env
  JWT=$(openssl rand -hex 32)
  PG_PW=$(openssl rand -hex 16)
  MINIO_PW=$(openssl rand -hex 16)
  # openssl rand -hex emits [0-9a-f] only, so '|' is a safe sed delimiter.
  sed_i "s|^API_JWT_SECRET=.*$|API_JWT_SECRET=${JWT}|" .env
  sed_i "s|^POSTGRES_PASSWORD=.*$|POSTGRES_PASSWORD=${PG_PW}|" .env
  sed_i "s|^MINIO_SECRET_KEY=.*$|MINIO_SECRET_KEY=${MINIO_PW}|" .env
  echo "  .env created. Fill in TG_API_ID, TG_API_HASH, TG_PHONE, TG_BOT_TOKEN before running ingester."
else
  echo "→ .env already exists, leaving untouched"
fi

echo "→ Building images"
docker compose build api ingester

echo "→ Starting infra services"
docker compose up -d postgres redis minio

echo "→ Waiting for postgres to be healthy"
for i in {1..30}; do
  # Docker Compose v2 Go-template avoids the python3 dependency entirely.
  status=$(docker compose ps postgres --format "{{.Health}}" 2>/dev/null || echo "unknown")
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done

echo "→ Bringing up api (will run migrations on boot — see Task 31)"
docker compose up -d api

echo "✓ Bootstrap complete. Try: make logs"
