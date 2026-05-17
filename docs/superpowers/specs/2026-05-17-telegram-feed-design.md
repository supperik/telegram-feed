# Telegram Feed — Design Document (MVP)

**Status:** Approved
**Date:** 2026-05-17
**Author:** Initial design via brainstorming session

---

## 1. Context and goal

### 1.1 Business problem

Telegram users subscribed to many channels suffer from information overload. They want to scroll through posts from selected channels in one clean interface with quick view, save, hide, and filter actions, without opening each channel separately.

### 1.2 MVP scope (from business requirements)

- Telegram Mini App (TMA) launched inside Telegram.
- User authentication via Telegram.
- Feed view of posts from connected sources.
- Vertical scrolling of cards.
- Open original post in Telegram.
- Save post.
- Hide post or source.
- Source list management.
- Basic admin panel for system-wide channel management.
- Backend service for ingest, normalization, and storage.

### 1.3 Non-goals (explicitly out of MVP)

- Full-text search across posts.
- Channel categories or tags.
- Read/unread state tracking.
- Push notifications outside the app.
- Algorithmic feed / ML filtering.
- OPML / chat-folder import.
- Multiple ingester instances / sharding.
- Post archival / table partitioning.
- Custom themes (use native TMA theme).

---

## 2. Key decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Post source: MTProto via Telethon (userbot)** | Bot API requires the bot to be channel administrator. Our users are regular subscribers, not admins of channels like `@meduzaproject`. MTProto reads as a normal user → covers the primary use case. |
| 2 | **Backend: Python 3.12 + FastAPI + Telethon** | Most mature combination for Telegram work, async-first, large community of reference implementations. |
| 3 | **Frontend (TMA): React 18 + Vite + @telegram-apps/sdk-react** | Standard for TMA. Official SDK from Telegram, fast Vite builds, TypeScript out of the box. |
| 4 | **Multi-user from day one** | Reflects the target audience (users plural). Posts table is shared across users; user-specific state via join tables. |
| 5 | **Admin = separate sysadmin web** | Separate web SPA with own login + TOTP, not embedded in TMA. Clear boundary between user features and ops. |
| 6 | **Hosting: VPS + Docker Compose** | Predictable cost, full control. Critical for stateful userbot session. Also runs identically on a local dev machine (must be testable locally without VPS). |
| 7 | **Media: photos → MinIO, videos → thumb-only + open in Telegram** | Photos are small and frequent — download and store them on ingest. Videos can be ≥ 2GB — store only thumbnail and `tg_file_id`; in MVP, tapping a video opens the original post in the Telegram client. Backend video streaming proxy is documented as a post-MVP follow-up. |
| 8 | **Feed UX: scrollable list (Telegram-like)** | Familiar pattern, fast scanning of large volumes. Reels-style swipe rejected as slower for news consumption. |
| 9 | **Realtime: pull-to-refresh + refresh on focus** | News feed doesn't need sub-second latency. No WS/SSE infrastructure. |
| 10 | **Ingest: event-driven via `events.NewMessage`** | Telethon emits events for monitored channels. No polling. Backfill on new channel join via `iter_messages`. |
| 11 | **Architecture: split `ingester` worker + `api` (FastAPI), communicate via PostgreSQL** | userbot is a stateful long-lived process; API is stateless. Splitting them lets API restart freely without dropping Telegram session. Communication via DB keeps infrastructure minimal (no message broker for MVP). |

---

## 3. System architecture

### 3.1 Deploy topology

All services run as containers in a single `docker-compose` stack. The same stack runs locally for development with an override file.

```
┌─────────────────────────────────────────────────────────────┐
│                       VPS / dev machine                     │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   ingester   │    │     api      │    │  admin-web   │   │
│  │  (Telethon)  │    │  (FastAPI)   │    │  (React SPA) │   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘   │
│         │ INSERT post       │ SELECT/INSERT     │ admin     │
│         ▼                   ▼                   ▼           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              PostgreSQL 16 (main store)             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │    MinIO     │    │     Redis    │    │    nginx     │   │
│  │ (photos S3)  │    │ (cache/lock) │    │ (TLS, proxy) │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
          ▲                                  ▲
          │ MTProto                          │ HTTPS
          │                                  │
┌─────────┴───────┐                  ┌───────┴─────────────┐
│ Telegram MTProto│                  │ TMA in Telegram +   │
│      DCs        │                  │   admin-web in      │
└─────────────────┘                  │   regular browser   │
                                     └─────────────────────┘
```

### 3.2 Components

| Service | Stack | Responsibility | Deploy notes |
|---------|-------|----------------|--------------|
| `ingester` | Python 3.12 + Telethon | Holds userbot session, subscribes to `NewMessage` for active channels, normalizes and persists posts, downloads photos to MinIO. Also runs backfill for newly added channels. | 1 instance only. Bind-mounted volume for `*.session` file. |
| `api` | Python 3.12 + FastAPI + SQLAlchemy + Alembic | HTTP API for TMA and admin: `/auth/telegram`, `/feed`, `/sources`, `/saved`, `/posts/{id}`, `/media/{id}`, `/admin/*`. Stateless. | 1–N instances. |
| `tma` | React 18 + Vite + @telegram-apps/sdk-react + TanStack Query | TMA frontend. Built to static, served by nginx. | Static build. |
| `admin-web` | React (same stack, separate bundle, no TMA SDK) | Sysadmin SPA with password + TOTP login. | Static build. |
| `postgres` | PostgreSQL 16 | Single source of truth: posts, users, sources, saved, hidden, audit. | Volume. |
| `minio` | MinIO | S3-compatible storage for photos and video thumbnails. | Volume. |
| `redis` | Redis 7 | Feed page cache, JWT blacklist, distributed locks (backfill), rate limit. | Optional volume. |
| `nginx` | nginx | TLS termination (Let's Encrypt), reverse proxy to `api`, static serving for `tma` and `admin-web`. | — |

### 3.3 Service boundaries

- `api` and `ingester` communicate **only through PostgreSQL**. No direct calls, no shared in-memory state.
- `ingester` writes to: `channels`, `posts`, `media`, `channel_subscriptions`. Reads from: `channel_join_queue` (work queue).
- `api` writes to: `users`, `user_sources`, `user_saved`, `user_hidden_*`, `channel_join_queue` (enqueue), `admins`, `admin_actions`. Reads from all tables.
- Neither service writes to the other's domain.

### 3.4 External dependencies

- Telegram MTProto endpoints (via `ingester`).
- Telegram WebApp `initData` HMAC (validated by `api` against `BOT_TOKEN`).
- Let's Encrypt for TLS (mandatory: TMA refuses to load over plain HTTP).

---

## 4. Domain model

### 4.1 Entity overview

```
User ─────< UserSource >───── Channel ────< Post >──── Media
  │                              │
  ├──< UserSavedPost >── Post    └──< ChannelSubscription >── (ingest state)
  ├──< UserHiddenPost >── Post
  └──< UserHiddenChannel >── Channel

Admin (sysadmin) — separate entity, never a User.
```

### 4.2 Schema

```sql
-- TMA users (one per Telegram user id)
users (
  id            BIGSERIAL PRIMARY KEY,
  tg_user_id    BIGINT UNIQUE NOT NULL,
  tg_username   TEXT,
  tg_first_name TEXT,
  tg_photo_url  TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  last_seen_at  TIMESTAMPTZ
)

-- Channels (shared across users)
channels (
  id            BIGSERIAL PRIMARY KEY,
  tg_chat_id    BIGINT UNIQUE NOT NULL,
  username      TEXT UNIQUE,
  title         TEXT NOT NULL,
  description   TEXT,
  photo_url     TEXT,
  posts_count   INTEGER DEFAULT 0,
  banned        BOOLEAN DEFAULT false,
  banned_reason TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  last_post_at  TIMESTAMPTZ
)

-- Userbot subscription state per channel
channel_subscriptions (
  channel_id    BIGINT PRIMARY KEY REFERENCES channels(id),
  status        TEXT NOT NULL,    -- 'pending_backfill' | 'active' | 'failed' | 'left'
  ref_count     INTEGER NOT NULL DEFAULT 0,
  last_error    TEXT,
  joined_at     TIMESTAMPTZ,
  backfilled_at TIMESTAMPTZ
)

-- Work queue for new channels requested by users
channel_join_queue (
  id                   BIGSERIAL PRIMARY KEY,
  channel_username     TEXT NOT NULL,
  requested_by_user_id BIGINT REFERENCES users(id),
  status               TEXT NOT NULL,   -- 'pending' | 'done' | 'failed'
  error_reason         TEXT,
  channel_id           BIGINT REFERENCES channels(id),
  created_at           TIMESTAMPTZ DEFAULT now(),
  updated_at           TIMESTAMPTZ
)

-- User's personal source list
user_sources (
  user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
  channel_id BIGINT REFERENCES channels(id),
  added_at   TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, channel_id)
)

-- Posts (shared)
posts (
  id             BIGSERIAL PRIMARY KEY,
  channel_id     BIGINT NOT NULL REFERENCES channels(id),
  tg_message_id  INTEGER NOT NULL,
  text           TEXT,
  text_html      TEXT,
  posted_at      TIMESTAMPTZ NOT NULL,
  edited_at      TIMESTAMPTZ,
  views          INTEGER,
  forwards       INTEGER,
  fetched_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (channel_id, tg_message_id)
)
CREATE INDEX posts_feed_idx ON posts (channel_id, posted_at DESC);

-- Media attached to posts (multiple per post for albums)
media (
  id           BIGSERIAL PRIMARY KEY,
  post_id      BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  type         TEXT NOT NULL,        -- 'photo' | 'video' | 'document'
  storage_key  TEXT,                  -- MinIO key (photos, video thumbs)
  tg_file_id   TEXT,                  -- for on-demand video proxy
  width        INTEGER,
  height       INTEGER,
  duration     INTEGER,
  size_bytes   BIGINT,
  position     SMALLINT DEFAULT 0
)

-- User-specific actions
user_saved (
  user_id  BIGINT REFERENCES users(id) ON DELETE CASCADE,
  post_id  BIGINT REFERENCES posts(id) ON DELETE CASCADE,
  saved_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, post_id)
)

user_hidden_posts (
  user_id   BIGINT REFERENCES users(id) ON DELETE CASCADE,
  post_id   BIGINT REFERENCES posts(id) ON DELETE CASCADE,
  hidden_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, post_id)
)

user_hidden_channels (
  user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
  channel_id BIGINT REFERENCES channels(id),
  hidden_at  TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, channel_id)
)

-- Sysadmin
admins (
  id            BIGSERIAL PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,         -- argon2
  totp_secret   TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
)

admin_actions (
  id         BIGSERIAL PRIMARY KEY,
  admin_id   BIGINT REFERENCES admins(id),
  action     TEXT NOT NULL,
  target     JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
)
```

### 4.3 Invariants

- `posts(channel_id, tg_message_id)` is unique. A given Telegram message is stored exactly once regardless of how many users subscribe to its channel. Ingest uses `ON CONFLICT DO NOTHING`.
- `channel_subscriptions.ref_count` reflects how many users currently have the channel in `user_sources`. **Maintained by `api`** in the same transaction as the `INSERT`/`DELETE` on `user_sources`. When the counter reaches zero, ingester observes it via a periodic sweep (every 5 minutes) and calls `LeaveChannel` (best-effort, not load-bearing for correctness).
- `users.last_seen_at` is updated by an `api` dependency on every authenticated request (throttled to one DB write per minute per user via Redis).
- `api` never writes to `posts`. `ingester` never writes to `users.*`.

### 4.4 Central feed query

```sql
SELECT p.*, c.title, c.username
FROM posts p
JOIN channels c        ON c.id = p.channel_id
JOIN user_sources us   ON us.channel_id = p.channel_id AND us.user_id = :user_id
WHERE c.banned = false
  AND NOT EXISTS (
    SELECT 1 FROM user_hidden_channels WHERE user_id = :user_id AND channel_id = p.channel_id
  )
  AND NOT EXISTS (
    SELECT 1 FROM user_hidden_posts WHERE user_id = :user_id AND post_id = p.id
  )
  AND (p.posted_at, p.id) < (:cursor_posted_at, :cursor_post_id)
ORDER BY p.posted_at DESC, p.id DESC
LIMIT :limit;
```

Keyset pagination on `(posted_at, id)` for stable cursors. First page uses `(NOW() + interval '1 day', 0)` as the cursor.

---

## 5. Key flows

### 5.1 Authentication

```
TMA loads inside Telegram → reads Telegram.WebApp.initData
       │
       ▼
POST /auth/telegram { init_data: "..." }
       │
       │  api verifies:
       │   1. HMAC-SHA256(init_data, secret_key) == hash,
       │      secret_key = HMAC-SHA256("WebAppData", BOT_TOKEN)
       │   2. auth_date is fresh (< 24h)
       │  users.upsert(tg_user_id, ...)
       ▼
{ access_token (JWT, 1h), refresh_token (7d) }
       │
       ▼
Every subsequent request: Authorization: Bearer <access_token>
```

`initData` verification implemented as a small (≈30 LOC) shared utility, no OAuth flow.

### 5.2 Adding a source

```
TMA: user types @meduzaproject → tap "Add"
       │
       ▼
POST /sources { username: "meduzaproject" }
       │
       │  api:
       │   1. SELECT FROM channels WHERE username = ?
       │   2a. If exists and not banned → INSERT user_sources, ref_count++, return 200
       │   2b. Else → INSERT channel_join_queue(status='pending'), return 202 + queue_id
       │
       ▼
ingester (polls channel_join_queue every 2s for status='pending'):
   - client.get_entity('@meduzaproject')
   - client(JoinChannelRequest(channel))
   - UPSERT channels(...)
   - INSERT channel_subscriptions(status='pending_backfill', ref_count=1)
   - UPDATE channel_join_queue.status='done', channel_id=...
   - Backfill: iter_messages(channel, limit=50) → INSERT posts + media
   - UPDATE channel_subscriptions SET status='active', backfilled_at=now()

TMA polls GET /sources/{queue_id}/status until status != 'pending'.
```

Error cases:
- Channel does not exist → `failed` with reason `username_not_occupied`.
- Channel is private → `failed` with reason `private_channel_unsupported` (MVP supports public only).
- FloodWaitError → ingester sleeps and retries with exponential backoff.
- userbot banned in channel → `failed` with reason.

### 5.3 Feed delivery

```
GET /feed?cursor=<base64>&limit=20
       │
       │  api:
       │   1. Decode cursor → (posted_at, post_id) or sentinel
       │   2. Run central feed query
       │   3. Load media[] for each post, annotate is_saved / is_hidden
       │   4. Cache page in Redis 30s (key: user_id + cursor)
       ▼
{ posts: [... up to 20 ...], next_cursor: "..." | null }

TMA renders cards, IntersectionObserver on last card → fetch next page.
Pull-to-refresh → GET /feed without cursor → new first page.

Actions:
- POST /posts/{id}/save        → INSERT user_saved (idempotent)
- DELETE /posts/{id}/save      → DELETE user_saved
- POST /posts/{id}/hide        → INSERT user_hidden_posts
- POST /sources/{id}/hide      → INSERT user_hidden_channels
- Tap post → tg://resolve?domain=...&post=... opens original in Telegram
```

All mutations are optimistic in the UI with rollback on error.

### 5.4 Media

**Photos** are downloaded during ingest:
```python
photo_bytes = await client.download_media(msg.photo, bytes)
key = f"photos/{channel_id}/{message_id}_{photo_id}.jpg"
minio.put_object("media", key, photo_bytes)
INSERT media(storage_key=key, tg_file_id=str(msg.photo.id), ...)
```
Frontend requests `GET /media/{media_id}` → `api` returns presigned URL (1h) → 302 redirect to MinIO.

**Videos** store only the thumbnail + `tg_file_id`:
```python
thumb_bytes = await client.download_media(msg.video.thumbs[-1], bytes)
minio.put_object("media", thumb_key, thumb_bytes)
INSERT media(type='video', storage_key=thumb_key, tg_file_id=str(msg.video.id), duration=...)
```

In the feed: thumbnail + play icon + duration badge. On click, MVP opens the original post in Telegram via `tg://resolve?domain=...&post=...`. A streaming proxy through `api` ↔ `ingester` is listed as a post-MVP follow-up in §7.

### 5.5 Sysadmin

The first admin is created by `infra/scripts/bootstrap.sh`: the script prompts for an email and password, generates a TOTP secret, prints the QR code to stdout, and inserts the row into `admins`. No web-based registration — admins are provisioned out-of-band.

```
POST /admin/login { email, password, totp }
   → admin-JWT (separate issuer from user JWT)

GET  /admin/channels                — all channels with metrics
POST /admin/channels/{id}/ban       — channels.banned=true
POST /admin/channels/{id}/unban
GET  /admin/stats                   — total users, posts, channels, ingester health
GET  /admin/ingester/health         — connected? floodwait? backfill queue depth?
POST /admin/ingester/restart        — signal via Redis
GET  /admin/admin-actions           — audit trail
```

### 5.6 Resilience

- **FloodWait**: ingester catches `FloodWaitError`, `asyncio.sleep(e.seconds + 1)`, retries.
- **Restart catchup**: on ingester boot, for each `channel_subscriptions` with `status='active'`, run `iter_messages(min_id=max_known_message_id, limit=100)` before subscribing to `NewMessage`. Ensures no posts are lost during downtime.
- **Dedup**: `posts.UNIQUE(channel_id, tg_message_id)` + `ON CONFLICT DO NOTHING` makes ingest idempotent.
- **Single ingester**: MVP assumes one userbot process. If horizontal scaling becomes necessary, shard by `channel_id % N`.

---

## 6. Cross-cutting concerns

### 6.1 Repository layout (monorepo)

```
telegram-feed/
├── README.md
├── docs/
│   ├── superpowers/specs/
│   └── architecture/
├── docker-compose.yml
├── docker-compose.override.yml
├── .env.example
├── .gitignore
├── Makefile
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/
│   ├── src/
│   │   ├── shared/         # db, models, config, storage, logging
│   │   ├── api/            # FastAPI app
│   │   │   ├── main.py
│   │   │   ├── deps.py
│   │   │   ├── routers/    # auth, feed, sources, posts, media, admin/
│   │   │   ├── services/   # business logic
│   │   │   └── schemas/    # pydantic DTOs
│   │   └── ingester/
│   │       ├── main.py
│   │       ├── client.py
│   │       ├── handlers.py
│   │       ├── join_worker.py
│   │       ├── backfill.py
│   │       ├── catchup.py
│   │       └── normalize.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
│
├── frontend/
│   ├── tma/                # Telegram Mini App
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── src/
│   │   │   ├── app/        # routing, providers
│   │   │   ├── features/   # feed, sources, saved, auth
│   │   │   ├── shared/     # api, ui, lib
│   │   │   └── main.tsx
│   │   └── tests/
│   └── admin/              # sysadmin SPA (same stack, no TMA SDK)
│
└── infra/
    ├── nginx/
    ├── postgres/init.sql
    └── scripts/
        ├── bootstrap.sh
        └── tunnel.sh
```

Boundary rules:
- `backend/src/api` and `backend/src/ingester` import only from `backend/src/shared`, never from each other.
- `frontend/tma` and `frontend/admin` are independent npm projects.
- Single Alembic project owns the DB schema.
- OpenAPI is generated from FastAPI and consumed by the frontends via `openapi-typescript` for end-to-end type safety.

### 6.2 Error handling

**Backend (FastAPI):**
- Domain exceptions are mapped to structured HTTP errors:
  ```json
  { "error": { "code": "channel_not_found", "message": "...", "details": {...} } }
  ```
- Global exception handler catches uncaught errors, logs with `request_id`, returns 500 without leaking internals.
- `structlog` JSON logs, correlation IDs propagate between services.

**Ingester:**
- `FloodWaitError` → sleep + retry.
- `ChannelPrivateError`, `UsernameNotOccupiedError`, `UsernameInvalidError` → mark queue row failed with reason.
- Any other exception inside a handler → log + skip that message; never crash the event loop.
- Internal healthcheck endpoint reports `last_new_message_at` and connection status.

**TMA:**
- React Error Boundary per feature section.
- TanStack Query retry + offline mode.
- Optimistic mutations with rollback + user-visible toast on failure.

### 6.3 Testing strategy (TDD per unified-workflow)

| Level | Scope | Tools |
|-------|-------|-------|
| Unit (backend) | Pure functions: normalize, JWT, initData verification, feed-SQL builder | pytest, hypothesis |
| Integration (backend) | Real PostgreSQL + MinIO via `pytest-docker`, Telethon mocked with `AsyncMock`. Scenarios: add source happy/sad paths, feed pagination, save/hide | pytest |
| E2E ingester | Inject fake `Update` into Telethon client via monkeypatch → assert DB rows appear | pytest |
| Frontend unit | Hooks, utilities, mappers | vitest |
| Frontend component | PostCard, FeedScreen, SourceList | vitest + React Testing Library |
| Frontend E2E | Open app, swipe, save, add source — mocked Telegram WebApp object | Playwright |

TDD red-green-refactor cycle applies to all production code per the unified workflow.

### 6.4 Local development workflow

Local parity with production is a hard requirement. Same `docker-compose.yml` runs locally with `docker-compose.override.yml` adding bind mounts, exposed ports, and reload flags.

```
make bootstrap       # generate .env, start db, run migrations, seed
make up              # docker-compose up (dev mode, hot reload)
make tunnel          # cloudflared tunnel → https://<random>.trycloudflare.com
                     # paste this URL into @BotFather (Bot Settings → Mini Apps → Configure)
                     # then open the test bot in Telegram and tap the menu button
make test            # pytest + vitest
make test-e2e        # playwright against local stack
make logs            # tail all containers
make ingester-shell  # python -m ingester.repl for live debugging
```

For TMA debugging, `cloudflared tunnel` exposes the local nginx over HTTPS. Telegram refuses `http://localhost`, so this tunnel is the only mechanism for full end-to-end testing locally. A test bot (separate from production) is registered in BotFather with the tunnel URL.

### 6.5 Security

- **TMA initData**: HMAC-SHA256 validation on every `/auth/*` request. JWT HS256, 1h access, 7d refresh.
- **Admin auth**: argon2 (memory=64MB, time=3) + TOTP 2FA. Rate-limited by email via Redis.
- **CORS**: `https://web.telegram.org` for `/api/*`, admin domain for `/admin/*`. No wildcards.
- **Secrets**: `.env` is gitignored. In production, mounted as docker secrets. Pydantic-settings validates required vars at startup.
- **userbot session**: `*.session` file is 0600 on disk, in a named volume, never committed.
- **Rate limit**: `/auth/telegram` ≤ 5/min per IP, `POST /sources` ≤ 30/h per user.
- **Content moderation**: out of MVP. Sysadmin can ban channels; per-post moderation is a follow-up.

### 6.6 Observability (MVP minimum)

- `structlog` JSON logs across all services, viewable via `docker logs` initially.
- Healthcheck endpoints for `api` and `ingester` wired into docker-compose.
- Optional: Sentry SDK for error reporting (backend and frontend).
- Health proxies: `channels.last_post_at` and `users.last_seen_at` as cheap activity signals, shown in admin dashboard.

---

## 7. Open follow-ups (post-MVP)

These are noted here so they aren't lost, but are explicitly **not** part of this spec's implementation plan:

- Full-text search across posts (`pg_trgm` or Meilisearch).
- Push notifications via the bot (DM with daily digest or per-post alert).
- Read/unread state.
- Video streaming proxy through `api` ↔ `ingester`.
- Multiple ingester instances with channel-id sharding.
- Old-post archival job / `posts` partitioning.
- OPML / chat-folder import.
- Channel categories and per-category filters.

---

## 8. Glossary

- **TMA** — Telegram Mini App, a web app loaded inside the Telegram client.
- **initData** — signed string Telegram passes to a TMA on launch, used for user authentication.
- **userbot** — a regular Telegram user account driven programmatically via MTProto (Telethon).
- **MTProto** — Telegram's transport protocol, accessible to user accounts (unlike Bot API which is bot-only).
- **Backfill** — fetching historical posts from a newly added channel before the userbot starts receiving live `NewMessage` events.
- **Catchup** — on ingester restart, fetching messages that arrived during downtime before resubscribing to live events.
