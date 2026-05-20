from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.channel_photo import channel_photo_url
from api.deps import get_current_user, get_db, get_redis
from api.pagination import FeedCursor
from api.schemas.feed import (
    FeedChannel,
    FeedMedia,
    FeedPage,
    FeedPost,
    ReadRequest,
    ReadResponse,
)
from shared.models import User
from shared.repositories.feed import fetch_feed_page
from shared.repositories.user_read_posts import bulk_mark_read

router = APIRouter(prefix="/feed", tags=["feed"])


CACHE_TTL_SECONDS = 30


@router.get("", response_model=FeedPage)
async def get_feed(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    include_read: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> FeedPage:
    cursor_obj = FeedCursor.decode(cursor) if cursor else FeedCursor.initial()
    # INITIAL page must reflect freshly-ingested posts on Refresh, so it is
    # never cached. Paginated pages (cursor != None) are safe to cache: under
    # keyset pagination the slice below a given cursor is immutable. The debug
    # ?include_read path is never cached — the cache key does not encode
    # include_read, so caching it would poison the default-path slice.
    cache_key = (
        f"feed:{user.id}:{cursor}:{limit}" if cursor and not include_read else None
    )
    if cache_key is not None:
        cached = await redis.get(cache_key)
        if cached:
            return FeedPage.model_validate_json(cached)

    rows = await fetch_feed_page(
        db,
        user_id=user.id,
        cursor_posted_at=cursor_obj.posted_at,
        cursor_post_id=cursor_obj.post_id,
        limit=limit,
        include_read=include_read,
    )
    posts = [
        FeedPost(
            id=row.post_id,
            tg_message_id=row.tg_message_id,
            posted_at=row.posted_at,
            text=row.text,
            text_html=row.text_html,
            views=row.views,
            forwards=row.forwards,
            channel=FeedChannel(
                id=row.channel_id,
                tg_chat_id=row.channel_tg_chat_id,
                username=row.channel_username,
                title=row.channel_title,
                photo_url=channel_photo_url(row.channel_id, row.channel_photo_storage_key),
                invite_url=(
                    f"https://t.me/+{row.channel_invite_hash}"
                    if row.channel_invite_hash
                    else None
                ),
            ),
            media=[
                FeedMedia(
                    id=m.id,
                    type=m.type,
                    width=m.width,
                    height=m.height,
                    duration=m.duration,
                    has_video_file=bool(m.video_storage_key),
                )
                for m in row.media
            ],
            is_saved=row.is_saved,
        )
        for row in rows
    ]
    if posts:
        last = posts[-1]
        next_cursor = FeedCursor(posted_at=last.posted_at, post_id=last.id).encode()
    else:
        next_cursor = None
    page = FeedPage(posts=posts, next_cursor=next_cursor)
    if cache_key is not None:
        await redis.set(cache_key, page.model_dump_json(), ex=CACHE_TTL_SECONDS)
    return page


async def _invalidate_feed_cache(redis: Redis, user_id: int) -> None:
    # Drop cached paginated pages so a now-read post does not resurface from a
    # stale slice. The initial page is never cached, so Refresh is unaffected.
    keys = [key async for key in redis.scan_iter(match=f"feed:{user_id}:*")]
    if keys:
        await redis.delete(*keys)


@router.post("/read", response_model=ReadResponse)
async def mark_read(
    body: ReadRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> ReadResponse:
    marked = await bulk_mark_read(db, user_id=user.id, post_ids=body.post_ids)
    await db.commit()
    await _invalidate_feed_cache(redis, user.id)
    return ReadResponse(marked=marked)
