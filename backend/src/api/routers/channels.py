"""Channel-scoped endpoints.

GET /channels/{channel_id}/photo — stream the cached avatar from MinIO.
JWT auth is accepted via `?token=…` query string (for `<img>` tags) OR
an Authorization Bearer header (for `fetch` calls); query takes
precedence. Mirrors the contract of GET /media/{id} so the TMA can use
the same auth wrapper for both.
"""
from __future__ import annotations

from typing import Iterator, Literal

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.channel_photo import channel_photo_url
from api.deps import get_current_user, get_db, get_settings
from api.errors import APIError
from api.pagination import CatalogCursor
from api.schemas.channels import CatalogChannelItem, CatalogPage
from api.schemas.sources import ChannelSummary
from shared.auth.jwt import decode_access
from shared.config import Settings
from shared.models import Channel, User
from shared.repositories.channel_catalog import (
    list_catalog_available,
    list_catalog_hidden,
)
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


@router.get("/catalog", response_model=CatalogPage)
async def get_catalog(
    view: Literal["available", "hidden"] = Query(default="available"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    q: str | None = Query(default=None, max_length=128),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CatalogPage:
    if cursor is None:
        cursor_obj = (
            CatalogCursor.initial_available()
            if view == "available"
            else CatalogCursor.initial_hidden()
        )
    else:
        cursor_obj = CatalogCursor.decode(cursor)
        if cursor_obj.view != view:
            raise APIError(
                code="bad_cursor",
                message="Cursor view does not match request",
                status_code=400,
            )

    if view == "available":
        rows = await list_catalog_available(
            db, user_id=user.id, cursor=cursor_obj, limit=limit, q=q,
        )
    else:
        rows = await list_catalog_hidden(
            db, user_id=user.id, cursor=cursor_obj, limit=limit, q=q,
        )

    items = [
        CatalogChannelItem(
            channel=ChannelSummary(
                id=r.channel_id,
                username=r.username,
                title=r.title,
                photo_url=channel_photo_url(r.channel_id, r.photo_storage_key),
            ),
            subscribers_count=r.subscribers_count,
            last_post_at=r.last_post_at,
            is_subscribed=r.is_subscribed,
            is_hidden_from_catalog=r.is_hidden_from_catalog,
        )
        for r in rows
    ]

    next_cursor: str | None = None
    if len(rows) == limit:
        last = rows[-1]
        if view == "available":
            next_cursor = CatalogCursor.available(
                posts_count=last.posts_count, channel_id=last.channel_id,
            ).encode()
        else:
            assert last.hidden_at is not None
            next_cursor = CatalogCursor.hidden(
                hidden_at=last.hidden_at, channel_id=last.channel_id,
            ).encode()

    return CatalogPage(items=items, next_cursor=next_cursor)


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
