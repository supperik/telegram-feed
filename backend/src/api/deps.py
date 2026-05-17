from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.errors import APIError
from shared.auth.jwt import decode_access
from shared.config import Settings, get_settings as _get_settings_singleton
from shared.models import User


async def get_settings() -> Settings:
    return _get_settings_singleton()


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


async def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise APIError(code="unauthenticated", message="Bearer token required", status_code=401)
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    token = _parse_bearer(authorization)
    payload = decode_access(token, secret=settings.api_jwt_secret)
    user = await db.get(User, payload.user_id)
    if user is None:
        raise APIError(code="unauthenticated", message="User no longer exists", status_code=401)
    # Throttle last_seen_at updates to <= 1/min/user via Redis SETNX.
    key = f"last_seen:{user.id}"
    if await redis.set(name=key, value="1", ex=60, nx=True):
        from sqlalchemy import update
        from sqlalchemy.sql import func

        await db.execute(update(User).where(User.id == user.id).values(last_seen_at=func.now()))
        await db.commit()
    return user


async def get_current_admin(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI dependency: extract and validate an admin JWT from the
    Authorization header, return the Admin row.

    Used by every /admin/* mutation endpoint (added in P2).
    Raises 401 with {error: {code: ...}} envelope on any failure.
    """
    from sqlalchemy import select

    from api.jwt_admin import decode_admin_token
    from shared.models import Admin

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "missing_bearer"}},
        )
    token = authorization.split(None, 1)[1]
    try:
        payload = decode_admin_token(token, expected_type="access")
    except Exception:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_admin_token"}},
        )
    admin_id = int(payload["sub"])
    res = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = res.scalar_one_or_none()
    if admin is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "admin_not_found"}},
        )
    return admin
