from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db, get_settings
from api.errors import APIError
from shared.config import Settings
from shared.models import Media, User
from shared.storage import make_storage_client


router = APIRouter(prefix="/media", tags=["media"])

# Storage keys are immutable: photos/{channel_id}/{msg_id}_{photo_id}.jpg
# and video_thumbs/{channel_id}/{msg_id}_{video_id}.jpg — they encode tg
# identifiers, so the bytes at a given key never change. Cache aggressively.
_CACHE_HEADERS = {"Cache-Control": "public, max-age=2592000, immutable"}


@router.get("/{media_id}")
async def get_media(
    media_id: int,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),  # auth required, no extra check
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
