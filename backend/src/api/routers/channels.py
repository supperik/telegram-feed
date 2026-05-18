"""Channel-scoped endpoints.

GET /channels/{channel_id}/photo — stream the cached avatar from MinIO.
JWT auth is accepted via `?token=…` query string (for `<img>` tags) OR
an Authorization Bearer header (for `fetch` calls); query takes
precedence. Mirrors the contract of GET /media/{id} so the TMA can use
the same auth wrapper for both.
"""
from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_settings
from api.errors import APIError
from shared.auth.jwt import decode_access
from shared.config import Settings
from shared.models import Channel, User
from shared.storage import make_storage_client


router = APIRouter(prefix="/channels", tags=["channels"])

# Channel avatars change rarely but can change (admin updates the photo).
# Cache for a day, but make it revalidatable so a forced refresh is fast.
_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


async def _get_user_for_channel_photo(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> User:
    raw: str | None = token
    if not raw and authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
    if not raw:
        raise APIError(code="unauthenticated", message="Token required", status_code=401)
    payload = decode_access(raw, secret=settings.api_jwt_secret)
    user = await db.get(User, payload.user_id)
    if user is None:
        raise APIError(code="unauthenticated", message="User no longer exists", status_code=401)
    return user


@router.get("/{channel_id}/photo")
async def get_channel_photo(
    channel_id: int,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_get_user_for_channel_photo),
) -> StreamingResponse:
    channel = await db.get(Channel, channel_id)
    if channel is None or not channel.photo_storage_key:
        raise APIError(
            code="channel_photo_not_found",
            message="Channel photo not found",
            status_code=404,
        )

    client = make_storage_client()
    response = client.get_object(settings.minio_bucket, channel.photo_storage_key)

    def _iter() -> Iterator[bytes]:
        try:
            for chunk in response.stream(32 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return StreamingResponse(_iter(), media_type="image/jpeg", headers=_CACHE_HEADERS)
