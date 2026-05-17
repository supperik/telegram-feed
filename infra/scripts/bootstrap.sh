#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "→ Generating .env from .env.example"
  cp .env.example .env
  JWT=$(openssl rand -hex 32)
  PG_PW=$(openssl rand -hex 16)
  MINIO_PW=$(openssl rand -hex 16)
  python3 - <<PY
import re, pathlib, os
p = pathlib.Path(".env")
text = p.read_text()
text = re.sub(r"^API_JWT_SECRET=.*$",    f"API_JWT_SECRET={os.environ['JWT']}", text, flags=re.M)
text = re.sub(r"^POSTGRES_PASSWORD=.*$", f"POSTGRES_PASSWORD={os.environ['PG_PW']}", text, flags=re.M)
text = re.sub(r"^MINIO_SECRET_KEY=.*$",  f"MINIO_SECRET_KEY={os.environ['MINIO_PW']}", text, flags=re.M)
p.write_text(text)
PY
  export JWT PG_PW MINIO_PW
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
  status=$(docker compose ps --format json postgres 2>/dev/null | python3 -c 'import sys,json;
try:
  print(json.loads(sys.stdin.readline()).get("Health","unknown"))
except Exception:
  print("unknown")' 2>/dev/null || echo "unknown")
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done

echo "→ Bringing up api (will run migrations on boot — see Task 31)"
docker compose up -d api

echo "✓ Bootstrap complete. Try: make logs"
