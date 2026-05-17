from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from api.errors import APIError

ALGO = "HS256"


@dataclass(frozen=True)
class JWTPayload:
    user_id: int
    type: str  # "access" | "refresh"


def _encode(*, user_id: int, type_: str, secret: str, ttl_seconds: int) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": type_,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return pyjwt.encode(payload, secret, algorithm=ALGO)


def encode_access(*, user_id: int, secret: str, ttl_seconds: int) -> str:
    return _encode(user_id=user_id, type_="access", secret=secret, ttl_seconds=ttl_seconds)


def encode_refresh(*, user_id: int, secret: str, ttl_seconds: int) -> str:
    return _encode(user_id=user_id, type_="refresh", secret=secret, ttl_seconds=ttl_seconds)


def _decode(token: str, *, secret: str, expected_type: str) -> JWTPayload:
    try:
        data = pyjwt.decode(token, secret, algorithms=[ALGO])
    except pyjwt.ExpiredSignatureError as e:
        raise APIError(code="expired_token", message="Token expired", status_code=401) from e
    except pyjwt.InvalidTokenError as e:
        raise APIError(code="bad_token", message="Token is invalid", status_code=401) from e
    if data.get("type") != expected_type:
        raise APIError(code="bad_token", message="Wrong token type", status_code=401)
    try:
        uid = int(data["sub"])
    except (KeyError, ValueError) as e:
        raise APIError(code="bad_token", message="Missing subject", status_code=401) from e
    return JWTPayload(user_id=uid, type=expected_type)


def decode_access(token: str, *, secret: str) -> JWTPayload:
    return _decode(token, secret=secret, expected_type="access")


def decode_refresh(token: str, *, secret: str) -> JWTPayload:
    return _decode(token, secret=secret, expected_type="refresh")
