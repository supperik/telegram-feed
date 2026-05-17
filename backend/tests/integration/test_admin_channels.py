import asyncio
import uuid
from datetime import datetime, timezone

import pyotp
import pytest
from fastapi.testclient import TestClient


def _seed_admin(pg_container):
    from shared.admin_security.passwords import hash_password
    from shared.admin_security.totp import generate_totp_secret
    from shared.db import make_engine, make_session_factory
    from shared.models import Admin

    secret = generate_totp_secret()
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    password = "hunter2!"

    async def run():
        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            row = Admin(email=email, password_hash=hash_password(password), totp_secret=secret)
            s.add(row)
            await s.commit()
            await s.refresh(row)
        await engine.dispose()
        return {"id": row.id, "email": email, "password": password, "secret": secret}

    return asyncio.run(run())


def _login(client: TestClient, admin: dict) -> str:
    code = pyotp.TOTP(admin["secret"]).now()
    r = client.post("/admin/login", json={
        "email": admin["email"],
        "password": admin["password"],
        "totp": code,
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _seed_channels(pg_container, *, count: int = 3, with_banned: bool = True):
    from shared.db import make_engine, make_session_factory
    from shared.models import Channel, ChannelSubscription

    async def run():
        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        suffix = uuid.uuid4().hex[:6]
        out = []
        async with sf() as s:
            for i in range(count):
                ch = Channel(
                    tg_chat_id=-100_000_000 - hash(suffix + str(i)) % 10_000,
                    username=f"chan_{suffix}_{i}",
                    title=f"Channel {suffix} #{i}",
                    posts_count=10 * (i + 1),
                    banned=(with_banned and i == 0),
                    banned_reason="seeded" if (with_banned and i == 0) else None,
                    last_post_at=datetime(2026, 5, 17, 12, i, 0, tzinfo=timezone.utc),
                )
                s.add(ch)
                await s.flush()
                # Subscription row for ref_count.
                sub = ChannelSubscription(
                    channel_id=ch.id, status="active", ref_count=i + 1,
                )
                s.add(sub)
                out.append({"id": ch.id, "tg_chat_id": ch.tg_chat_id,
                            "username": ch.username, "title": ch.title})
            await s.commit()
        await engine.dispose()
        return out

    return asyncio.run(run())


@pytest.fixture
def admin_record(configured_env, pg_container):
    return _seed_admin(pg_container)


@pytest.fixture
def channels(configured_env, pg_container):
    return _seed_channels(pg_container, count=3, with_banned=True)


@pytest.mark.integration
def test_list_channels_requires_admin_auth(configured_env, admin_record, channels):
    from api.main import app
    with TestClient(app) as client:
        r = client.get("/admin/channels")
        assert r.status_code == 401
        assert r.json()["detail"]["error"]["code"] == "missing_bearer"


@pytest.mark.integration
def test_list_channels_happy_path(configured_env, admin_record, channels):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, admin_record)
        r = client.get("/admin/channels", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "channels" in body
        assert "next_cursor" in body
        ids_returned = [c["id"] for c in body["channels"]]
        assert all(c["id"] in ids_returned for c in channels)
        # Banned channel comes first (sort: banned DESC).
        assert body["channels"][0]["banned"] is True


@pytest.mark.integration
def test_list_channels_q_filter(configured_env, admin_record, channels):
    from api.main import app
    target = channels[1]
    with TestClient(app) as client:
        token = _login(client, admin_record)
        r = client.get(
            f"/admin/channels?q={target['username']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        ids = [c["id"] for c in body["channels"]]
        assert target["id"] in ids
        # Other channels not matching should be absent.
        other_ids = {c["id"] for c in channels if c["id"] != target["id"]}
        assert all(oid not in ids for oid in other_ids)


@pytest.mark.integration
def test_ban_channel_idempotent_and_writes_audit(configured_env, admin_record, channels):
    from sqlalchemy import select
    from shared.config import get_settings
    from shared.db import make_engine, make_session_factory
    from shared.models import AdminAction
    from api.main import app

    target = next(c for c in channels if c["title"].endswith("#2"))  # not pre-banned
    with TestClient(app) as client:
        token = _login(client, admin_record)
        r = client.post(
            f"/admin/channels/{target['id']}/ban",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "spam"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["banned"] is True
        assert body["banned_reason"] == "spam"

        # Idempotent — second ban with new reason updates reason and appends action.
        r2 = client.post(
            f"/admin/channels/{target['id']}/ban",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "abuse"},
        )
        assert r2.status_code == 200
        assert r2.json()["banned_reason"] == "abuse"

    async def fetch():
        get_settings.cache_clear()
        engine = make_engine(get_settings().postgres_dsn)
        sf = make_session_factory(engine)
        async with sf() as session:
            res = await session.execute(
                select(AdminAction)
                .where(AdminAction.action == "ban_channel")
                .order_by(AdminAction.id.asc())
            )
            actions = res.scalars().all()
        await engine.dispose()
        return actions

    actions = asyncio.run(fetch())
    # At least 2 ban actions exist for this channel.
    relevant = [a for a in actions if (a.target or {}).get("channel_id") == target["id"]]
    assert len(relevant) >= 2
    reasons = [a.target["reason"] for a in relevant]
    assert reasons == ["spam", "abuse"]


@pytest.mark.integration
def test_unban_channel_idempotent_and_writes_audit(configured_env, admin_record, channels):
    from sqlalchemy import select
    from shared.config import get_settings
    from shared.db import make_engine, make_session_factory
    from shared.models import AdminAction
    from api.main import app

    target_id = channels[0]["id"]  # the pre-banned one
    with TestClient(app) as client:
        token = _login(client, admin_record)
        r = client.post(
            f"/admin/channels/{target_id}/unban",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert r.status_code == 200, r.text
        assert r.json()["banned"] is False

        # Idempotent.
        r2 = client.post(
            f"/admin/channels/{target_id}/unban",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert r2.status_code == 200

    async def fetch():
        get_settings.cache_clear()
        engine = make_engine(get_settings().postgres_dsn)
        sf = make_session_factory(engine)
        async with sf() as session:
            res = await session.execute(
                select(AdminAction).where(AdminAction.action == "unban_channel")
            )
            actions = res.scalars().all()
        await engine.dispose()
        return actions

    actions = asyncio.run(fetch())
    relevant = [a for a in actions if (a.target or {}).get("channel_id") == target_id]
    assert len(relevant) >= 2  # idempotent → two actions


@pytest.mark.integration
def test_ban_404_for_unknown_channel(configured_env, admin_record):
    from api.main import app
    with TestClient(app) as client:
        token = _login(client, admin_record)
        r = client.post(
            "/admin/channels/999999/ban",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "x"},
        )
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "channel_not_found"


@pytest.mark.integration
def test_user_token_rejected_on_admin_endpoint(configured_env, admin_record, channels):
    """Cross-issuer protection: a user-side access token must not work here."""
    from shared.auth.jwt import encode_access
    from shared.config import get_settings
    from api.main import app

    get_settings.cache_clear()
    s = get_settings()
    # Token signed with the plain user secret (no ":admin" suffix). The admin
    # dependency must reject it because the HMAC key won't match.
    user_token = encode_access(
        user_id=1,
        secret=s.api_jwt_secret,
        ttl_seconds=s.api_jwt_access_ttl_seconds,
    )

    with TestClient(app) as client:
        r = client.get(
            "/admin/channels",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert r.status_code == 401
        assert "admin" in r.json()["detail"]["error"]["code"].lower()
