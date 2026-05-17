import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from fastapi.testclient import TestClient


def _seed_admin(pg_container, *, email_prefix="stats"):
    from shared.admin_security.passwords import hash_password
    from shared.admin_security.totp import generate_totp_secret
    from shared.db import make_engine, make_session_factory
    from shared.models import Admin

    secret = generate_totp_secret()
    email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com"

    async def run():
        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            row = Admin(email=email, password_hash=hash_password("hunter2!"), totp_secret=secret)
            s.add(row)
            await s.commit()
            await s.refresh(row)
        await engine.dispose()
        return {"id": row.id, "email": email, "password": "hunter2!", "secret": secret}

    return asyncio.run(run())


def _login(client: TestClient, admin: dict) -> str:
    code = pyotp.TOTP(admin["secret"]).now()
    r = client.post("/admin/login", json={
        "email": admin["email"], "password": admin["password"], "totp": code,
    })
    return r.json()["access_token"]


def _seed_stats_corpus(pg_container):
    """Insert 3 users, 4 channels (1 banned), 5 posts."""
    from shared.db import make_engine, make_session_factory
    from shared.models import Channel, Post, User

    async def run():
        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        suffix = uuid.uuid4().hex[:6]
        last_post_at = None
        async with sf() as s:
            for i in range(3):
                s.add(User(tg_user_id=10_000 + hash(suffix + str(i)) % 1_000, tg_username=f"u{suffix}{i}"))
            channels = []
            for i in range(4):
                ch = Channel(
                    tg_chat_id=-200_000_000 - hash(suffix + "c" + str(i)) % 10_000,
                    username=f"sc_{suffix}_{i}",
                    title=f"SC {i}",
                    banned=(i == 0),
                )
                s.add(ch)
                channels.append(ch)
            await s.flush()
            for i, ch in enumerate(channels[:3]):  # 3 channels get posts; one with 2 posts
                for j in range(2 if i == 0 else 1):
                    dt = datetime(2026, 5, 17, 12, i, j, tzinfo=timezone.utc)
                    if last_post_at is None or dt > last_post_at:
                        last_post_at = dt
                    s.add(Post(channel_id=ch.id, tg_message_id=1000 * i + j,
                               text=f"post {i}.{j}", posted_at=dt))
            await s.commit()
        await engine.dispose()

    asyncio.run(run())


@pytest.fixture
def stats_admin(configured_env, pg_container):
    _seed_stats_corpus(pg_container)
    return _seed_admin(pg_container)


@pytest.mark.integration
def test_stats_requires_admin_auth(configured_env, stats_admin):
    from api.main import app
    with TestClient(app) as client:
        r = client.get("/admin/stats")
        assert r.status_code == 401


@pytest.mark.integration
def test_stats_returns_counts(configured_env, stats_admin):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, stats_admin)
        r = client.get("/admin/stats", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        # The fixture seeds 3 users, 4 channels (1 banned), 4 posts (2+1+1).
        # But other tests may seed more; we assert minima.
        assert body["users_count"] >= 3
        assert body["channels_count"] >= 4
        assert body["banned_channels"] >= 1
        assert body["posts_count"] >= 4
        assert body["last_post_at"] is not None
