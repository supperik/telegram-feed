import hashlib
import hmac
import time
from urllib.parse import urlencode

import pytest

from shared.auth.initdata import VerifiedInitData, verify_init_data


BOT_TOKEN = "1234:test-bot-token"


def _sign(payload: dict[str, str], bot_token: str = BOT_TOKEN, *, drop_hash: bool = False) -> str:
    data = dict(payload)
    if drop_hash:
        data.pop("hash", None)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    pairs = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    return hmac.new(secret_key, pairs.encode(), hashlib.sha256).hexdigest()


def _make_init_data(now: int | None = None, bot_token: str = BOT_TOKEN) -> str:
    auth_date = now if now is not None else int(time.time())
    payload = {
        "auth_date": str(auth_date),
        "query_id": "AAH1234",
        "user": '{"id":7777,"first_name":"Ada","username":"ada","language_code":"en"}',
    }
    payload["hash"] = _sign(payload, bot_token=bot_token, drop_hash=False)  # hash signs sorted-non-hash fields
    # Trick: hash() above already signed without itself because we built the payload then signed THIS dict
    # before adding hash to it. Recompute correctly:
    h = _sign({k: v for k, v in payload.items() if k != "hash"}, bot_token=bot_token)
    payload["hash"] = h
    return urlencode(payload)


def test_verify_returns_user_on_valid() -> None:
    init = _make_init_data()
    v = verify_init_data(init, bot_token=BOT_TOKEN, max_age_seconds=24 * 3600)
    assert isinstance(v, VerifiedInitData)
    assert v.tg_user_id == 7777
    assert v.tg_first_name == "Ada"
    assert v.tg_username == "ada"


def test_verify_rejects_bad_hash() -> None:
    init = _make_init_data() + "x"  # tamper
    with pytest.raises(Exception) as excinfo:
        verify_init_data(init, bot_token=BOT_TOKEN, max_age_seconds=24 * 3600)
    assert "bad" in str(excinfo.value).lower() or "init" in str(excinfo.value).lower()


def test_verify_rejects_stale() -> None:
    init = _make_init_data(now=int(time.time()) - 25 * 3600)
    with pytest.raises(Exception):
        verify_init_data(init, bot_token=BOT_TOKEN, max_age_seconds=24 * 3600)


def test_verify_rejects_other_bot_token() -> None:
    init = _make_init_data()
    with pytest.raises(Exception):
        verify_init_data(init, bot_token="different:token", max_age_seconds=24 * 3600)
