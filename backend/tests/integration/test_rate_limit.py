"""Sliding-window rate limit tests for /auth/telegram and POST /sources.

Test settings shrink the windows to 3 requests so we don't hammer the
endpoint 30+ times. Defaults (5/min, 30/h) are validated in test_config.
"""
import hashlib
import hmac
import time
from urllib.parse import urlencode

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel


BOT_TOKEN = "1234:test-bot-token"
SECRET = "x" * 32


def _make_init_data(now: int | None = None, user_id: int = 999) -> str:
    auth_date = now if now is not None else int(time.time())
    payload = {
        "auth_date": str(auth_date),
        "query_id": "AAH",
        "user": '{"id":' + str(user_id) + ',"first_name":"Bob","username":"bob"}',
    }
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    payload["hash"] = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_telegram_under_limit_passes(async_client) -> None:
    # Three calls within the window must all succeed (limit=3 in test env).
    for i in range(3):
        init = _make_init_data(user_id=1000 + i)
        r = await async_client.post("/auth/telegram", json={"init_data": init})
        assert r.status_code == 200, f"call #{i + 1}: {r.status_code} {r.text}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_telegram_over_limit_returns_429(async_client) -> None:
    for i in range(3):
        init = _make_init_data(user_id=2000 + i)
        r = await async_client.post("/auth/telegram", json={"init_data": init})
        assert r.status_code == 200, f"setup call #{i + 1} should pass"

    init = _make_init_data(user_id=2999)
    r = await async_client.post("/auth/telegram", json={"init_data": init})
    assert r.status_code == 429, r.text
    body = r.json()
    assert body["error"]["code"] == "rate_limited"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_under_limit_passes(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=51)
    # Pre-create channels so /sources returns 200 (subscribed) instead of 202 (queued).
    for i in range(3):
        db_session.add(Channel(tg_chat_id=70000 + i, username=f"u_under_{i}", title=f"T{i}"))
    await db_session.commit()

    for i in range(3):
        r = await async_client.post(
            "/sources", json={"input": f"u_under_{i}"}, headers=_auth(user_id)
        )
        assert r.status_code == 200, f"call #{i + 1}: {r.status_code} {r.text}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_over_limit_returns_429(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=52)
    for i in range(3):
        db_session.add(Channel(tg_chat_id=80000 + i, username=f"u_over_{i}", title=f"T{i}"))
    await db_session.commit()

    for i in range(3):
        r = await async_client.post(
            "/sources", json={"input": f"u_over_{i}"}, headers=_auth(user_id)
        )
        assert r.status_code == 200, f"setup call #{i + 1} should pass"

    r = await async_client.post(
        "/sources", json={"input": "u_over_99"}, headers=_auth(user_id)
    )
    assert r.status_code == 429, r.text
    body = r.json()
    assert body["error"]["code"] == "rate_limited"
