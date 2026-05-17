import hashlib
import hmac
import time
from urllib.parse import urlencode

import pytest

from shared.auth.jwt import decode_access, decode_refresh


BOT_TOKEN = "1234:test-bot-token"


def _make_init_data(now: int | None = None) -> str:
    auth_date = now if now is not None else int(time.time())
    payload = {
        "auth_date": str(auth_date),
        "query_id": "AAH",
        "user": '{"id":999,"first_name":"Bob","username":"bob"}',
    }
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    payload["hash"] = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_telegram_issues_tokens(async_client) -> None:
    init = _make_init_data()
    r = await async_client.post("/auth/telegram", json={"init_data": init})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body and "refresh_token" in body
    access = decode_access(body["access_token"], secret="x" * 32)
    refresh = decode_refresh(body["refresh_token"], secret="x" * 32)
    assert access.user_id == refresh.user_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_telegram_rejects_bad_hash(async_client) -> None:
    init = _make_init_data() + "garbage"
    r = await async_client.post("/auth/telegram", json={"init_data": init})
    assert r.status_code == 401
    assert r.json()["error"]["code"] in {"bad_init_data", "stale_init_data"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_refresh_happy_path(async_client) -> None:
    init = _make_init_data()
    r1 = await async_client.post("/auth/telegram", json={"init_data": init})
    refresh = r1.json()["refresh_token"]

    r2 = await async_client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200, r2.text
    assert "access_token" in r2.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_refresh_rejects_access_token(async_client) -> None:
    init = _make_init_data()
    r1 = await async_client.post("/auth/telegram", json={"init_data": init})
    access = r1.json()["access_token"]

    r2 = await async_client.post("/auth/refresh", json={"refresh_token": access})
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "bad_token"
