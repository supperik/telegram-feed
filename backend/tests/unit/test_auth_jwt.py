import time

import pytest

from api.errors import APIError
from shared.auth.jwt import (
    JWTPayload,
    decode_access,
    decode_refresh,
    encode_access,
    encode_refresh,
)


SECRET = "x" * 32


def test_access_roundtrip() -> None:
    tok = encode_access(user_id=42, secret=SECRET, ttl_seconds=60)
    p = decode_access(tok, secret=SECRET)
    assert p.user_id == 42
    assert p.type == "access"


def test_refresh_roundtrip() -> None:
    tok = encode_refresh(user_id=42, secret=SECRET, ttl_seconds=600)
    p = decode_refresh(tok, secret=SECRET)
    assert p.user_id == 42
    assert p.type == "refresh"


def test_access_token_rejected_as_refresh() -> None:
    tok = encode_access(user_id=42, secret=SECRET, ttl_seconds=60)
    with pytest.raises(APIError) as excinfo:
        decode_refresh(tok, secret=SECRET)
    assert excinfo.value.code == "bad_token"


def test_decode_rejects_wrong_secret() -> None:
    tok = encode_access(user_id=42, secret=SECRET, ttl_seconds=60)
    with pytest.raises(APIError):
        decode_access(tok, secret="y" * 32)


def test_expired_access_rejected() -> None:
    tok = encode_access(user_id=42, secret=SECRET, ttl_seconds=-1)
    time.sleep(0.01)
    with pytest.raises(APIError) as excinfo:
        decode_access(tok, secret=SECRET)
    assert excinfo.value.code in {"expired_token", "bad_token"}
