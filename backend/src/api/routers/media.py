from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db, get_settings
from api.errors import APIError
from api.presign import presigned_get
from shared.config import Settings
from shared.models import Media, User
from shared.storage import make_storage_client


router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{media_id}")
async def get_media(
    media_id: int,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),  # auth required, no extra check
) -> RedirectResponse:
    media = await db.get(Media, media_id)
    if media is None or not media.storage_key:
        raise APIError(code="media_not_found", message="Media not found", status_code=404)
    client = make_storage_client()
    url = presigned_get(
        client, bucket=settings.minio_bucket, key=media.storage_key, expires_seconds=3600
    )
    return RedirectResponse(url=url, status_code=302)
