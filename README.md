# telegram-feed

Telegram Mini App that aggregates posts from selected Telegram channels into a single feed.

## Production deployment

See [`RUNBOOK-prod.md`](RUNBOOK-prod.md) for a step-by-step guide from a fresh Ubuntu 24.04 VDS to a working stack on `zupperik.dev` (TMA) and `admin.zupperik.dev` (admin SPA), including Let's Encrypt, Telethon SMS login, and BotFather setup.

## Local development quickstart

Prereqs: Docker Desktop, Python 3.12 on host, Poetry (one-time: `py -3.12 -m pip install --user poetry`).

```bash
make bootstrap          # generates .env, builds images, starts infra services
docker compose up -d api
docker compose exec api alembic upgrade head
curl http://localhost:8000/internal/health
```

To wipe everything (Postgres data, MinIO buckets, Telegram session) and start fresh: `docker compose down -v`.

To run the userbot, fill in `TG_API_ID`, `TG_API_HASH`, `TG_PHONE` in `.env` (get them at https://my.telegram.org/apps), then:

```bash
docker compose up -d ingester
docker compose logs -f ingester
```

The first connection prompts for the SMS code via stdin — attach an interactive terminal: `docker compose run --rm ingester python -m ingester.main`.

To expose the TMA over HTTPS during local development, use `cloudflared tunnel --url http://localhost:80` and register the resulting URL with @BotFather as the Mini App URL.

## Tests

```bash
make test               # full backend suite (unit + integration via testcontainers)
make test-unit          # unit only — no Docker needed
make test-integration   # integration — requires Docker
```

Integration tests run testcontainers-managed Postgres. On Windows + Docker Desktop, the Ryuk reaper is disabled (`TESTCONTAINERS_RYUK_DISABLED=true` in `backend/tests/conftest.py`) to work around a port-binding flake; cleanup happens via the standard testcontainers context manager.

## Project layout

- `backend/` — FastAPI API + Telethon ingester (Python 3.12, Poetry).
  - `src/shared/` — config, logging, db, storage, redis, models (12 SQLAlchemy 2.0 entities).
  - `src/api/` — FastAPI app; `/internal/health` lives here today.
  - `src/ingester/` — Telethon worker.
  - `migrations/` — Alembic with async env.py.
  - `tests/{unit,integration,smoke}/`.
- `frontend/tma/` — Telegram Mini App (scaffolded in a later plan).
- `frontend/admin/` — Sysadmin web (scaffolded in a later plan).
- `infra/` — nginx config, Postgres init, bootstrap script.
- `docs/` — design specs and implementation plans (gitignored, local-only).

## Architecture summary

Split-process backend: `ingester` holds the long-lived Telethon session and writes posts to Postgres; `api` is stateless and serves the TMA and admin web. Both services share `backend/src/shared/`. Communication between them is via Postgres only (a work queue for new channel subscriptions and `posts`/`media` tables for ingested content). See `docs/superpowers/specs/2026-05-17-telegram-feed-design.md` for full design.

## Commit conventions

This project does not include AI attribution in commits (no `Co-Authored-By: Claude`, no `🤖 Generated with...` trailers). One commit per closed beads task.
