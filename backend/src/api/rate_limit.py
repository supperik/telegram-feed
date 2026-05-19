"""Sliding-window Redis rate limiter as a FastAPI dependency.

Design §6.5: POST /auth/telegram ≤ N/window/IP, POST /sources ≤ N/window/user.
The actual N and window are read from Settings so they're tunable per env
without redeploying.

Algorithm: per-key Redis sorted set keyed by request timestamp (ms).
The Lua script atomically (a) drops entries older than now-window,
(b) counts the remainder, (c) either rejects or appends a new member.
Atomicity matters — without Lua a burst could pass the count check before
either request appended its own entry.
"""
from __future__ import annotations

import time
import uuid

from fastapi import Depends, Request
from redis.asyncio import Redis

from api.deps import get_current_user, get_redis, get_settings
from api.errors import APIError
from shared.config import Settings
from shared.models import User


_LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local cutoff_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window_s = tonumber(ARGV[4])
local member = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, 0, cutoff_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
    return 0
end
redis.call('ZADD', key, now_ms, member)
redis.call('EXPIRE', key, window_s + 1)
return 1
"""


def _client_ip(request: Request) -> str:
    # nginx prod config sets X-Real-IP to $remote_addr (see infra/nginx/nginx.prod.conf).
    # X-Forwarded-For is appended; first entry is the originating client.
    real = request.headers.get("x-real-ip")
    if real:
        return real
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _get_script(redis: Redis):
    # Cache the Script object on the Redis client so we hit EVALSHA after the
    # first call instead of shipping the source on every check.
    cached = getattr(redis, "_rate_limit_script", None)
    if cached is None:
        cached = redis.register_script(_LUA_SLIDING_WINDOW)
        redis._rate_limit_script = cached  # type: ignore[attr-defined]
    return cached


async def _check_and_register(
    redis: Redis, *, key: str, limit: int, window_seconds: int
) -> bool:
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - window_seconds * 1000
    # Unique member so two requests with the same millisecond don't collide.
    member = f"{now_ms}-{uuid.uuid4().hex}"
    script = _get_script(redis)
    allowed = await script(
        keys=[key],
        args=[now_ms, cutoff_ms, limit, window_seconds, member],
    )
    return int(allowed) == 1


def _raise_rate_limited(scope: str, limit: int, window_seconds: int) -> None:
    raise APIError(
        code="rate_limited",
        message="Too many requests",
        status_code=429,
        details={"scope": scope, "limit": limit, "window_seconds": window_seconds},
    )


async def auth_ip_rate_limit(
    request: Request,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> None:
    ip = _client_ip(request)
    limit = settings.rate_limit_auth_per_window
    window = settings.rate_limit_auth_window_seconds
    key = f"rl:auth:{ip}"
    if not await _check_and_register(redis, key=key, limit=limit, window_seconds=window):
        _raise_rate_limited("auth", limit, window)


async def sources_user_rate_limit(
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> None:
    limit = settings.rate_limit_sources_per_window
    window = settings.rate_limit_sources_window_seconds
    key = f"rl:sources_add:{user.id}"
    if not await _check_and_register(redis, key=key, limit=limit, window_seconds=window):
        _raise_rate_limited("sources_add", limit, window)
