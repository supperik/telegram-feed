from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_settings
from api.errors import APIError
from shared.auth.jwt import decode_access
from shared.config import Settings
from shared.models import Media, User
from shared.storage import make_storage_client


router = APIRouter(prefix="/media", tags=["media"])

# Storage keys are immutable: photos/{channel_id}/{msg_id}_{photo_id}.jpg
# and video_thumbs/{channel_id}/{msg_id}_{video_id}.jpg — they encode tg
# identifiers, so the bytes at a given key never change. Cache aggressively.
_CACHE_HEADERS = {"Cache-Control": "public, max-age=2592000, immutable"}


async def _get_user_for_media(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Auth for media: accept JWT via ?token=... query (for <img> tags
    which can't send custom headers) OR via Authorization Bearer header
    (for fetch() calls). Query token takes precedence."""
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


@router.get("/{media_id}")
async def get_media(
    media_id: int,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_get_user_for_media),
) -> StreamingResponse:
    media = await db.get(Media, media_id)
    if media is None or not media.storage_key:
        raise APIError(code="media_not_found", message="Media not found", status_code=404)

    client = make_storage_client()
    response = client.get_object(settings.minio_bucket, media.storage_key)

    def _iter() -> Iterator[bytes]:
        try:
            for chunk in response.stream(32 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return StreamingResponse(_iter(), media_type="image/jpeg", headers=_CACHE_HEADERS)


@router.get("/{media_id}/video")
async def get_media_video(
    media_id: int,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_get_user_for_media),
) -> StreamingResponse:
    media = await db.get(Media, media_id)
    if media is None or media.type != "video" or not media.video_storage_key:
        raise APIError(code="media_not_found", message="Video not found", status_code=404)

    client = make_storage_client()
    response = client.get_object(settings.minio_bucket, media.video_storage_key)

    def _iter() -> Iterator[bytes]:
        try:
            for chunk in response.stream(64 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return StreamingResponse(_iter(), media_type="video/mp4", headers=_CACHE_HEADERS)
