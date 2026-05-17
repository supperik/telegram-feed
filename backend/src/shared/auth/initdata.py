from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from api.errors import APIError


@dataclass(frozen=True)
class VerifiedInitData:
    tg_user_id: int
    tg_username: str | None
    tg_first_name: str | None
    tg_photo_url: str | None
    auth_date: int


def verify_init_data(
    init_data: str, *, bot_token: str, max_age_seconds: int = 24 * 3600
) -> VerifiedInitData:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    supplied_hash = pairs.pop("hash", None)
    if not supplied_hash:
        raise APIError(code="bad_init_data", message="Missing hash", status_code=401)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    expected = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hash):
        raise APIError(code="bad_init_data", message="Bad initData signature", status_code=401)

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as e:
        raise APIError(code="bad_init_data", message="Bad auth_date", status_code=401) from e
    if auth_date <= 0 or (time.time() - auth_date) > max_age_seconds:
        raise APIError(code="stale_init_data", message="initData is stale", status_code=401)

    user_raw = pairs.get("user", "{}")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as e:
        raise APIError(code="bad_init_data", message="Bad user JSON", status_code=401) from e

    return VerifiedInitData(
        tg_user_id=int(user["id"]),
        tg_username=user.get("username"),
        tg_first_name=user.get("first_name"),
        tg_photo_url=user.get("photo_url"),
        auth_date=auth_date,
    )
