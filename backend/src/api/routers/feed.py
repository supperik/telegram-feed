from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.channel_photo import channel_photo_url
from api.deps import get_current_user, get_db, get_redis
from api.pagination import FeedCursor
from api.schemas.feed import FeedChannel, FeedMedia, FeedPage, FeedPost
from shared.models import User
from shared.repositories.feed import fetch_feed_page

router = APIRouter(prefix="/feed", tags=["feed"])


CACHE_TTL_SECONDS = 30


@router.get("", response_model=FeedPage)
async def get_feed(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> FeedPage:
    cursor_obj = FeedCursor.decode(cursor) if cursor else FeedCursor.initial()
    # INITIAL page must reflect freshly-ingested posts on Refresh, so it is
    # never cached. Paginated pages (cursor != None) are safe to cache: under
    # keyset pagination the slice below a given cursor is immutable.
    cache_key = f"feed:{user.id}:{cursor}:{limit}" if cursor else None
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
            ),
            media=[
                FeedMedia(
                    id=m.id,
                    type=m.type,
                    width=m.width,
                    height=m.height,
                    duration=m.duration,
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
