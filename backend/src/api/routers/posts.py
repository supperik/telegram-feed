from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.channel_photo import channel_photo_url
from api.deps import get_current_user, get_db
from api.errors import APIError
from api.pagination import PostListCursor
from api.schemas.feed import FeedChannel, FeedMedia, FeedPage, FeedPost
from shared.models import Post, User
from shared.repositories.feed import (
    FeedPostRow,
    fetch_hidden_posts_page,
    fetch_read_posts_page,
    fetch_saved_posts_page,
)
from shared.repositories.user_states import (
    hide_post as hide_post_repo,
)
from shared.repositories.user_states import (
    save_post,
    unhide_post,
    unsave_post,
)

router = APIRouter(prefix="/posts", tags=["posts"])


async def _require_post(db: AsyncSession, post_id: int) -> None:
    if await db.get(Post, post_id) is None:
        raise APIError(code="post_not_found", message="Post not found", status_code=404)


def _row_to_feed_post(row: FeedPostRow) -> FeedPost:
    return FeedPost(
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


def _build_page(rows: list[FeedPostRow]) -> FeedPage:
    posts = [_row_to_feed_post(r) for r in rows]
    if rows and rows[-1].sort_at is not None:
        last = rows[-1]
        next_cursor: str | None = PostListCursor(
            sort_at=last.sort_at, post_id=last.post_id
        ).encode()
    else:
        next_cursor = None
    return FeedPage(posts=posts, next_cursor=next_cursor)


@router.get("/saved", response_model=FeedPage)
async def list_saved(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedPage:
    cursor_obj = PostListCursor.decode(cursor) if cursor else PostListCursor.initial()
    rows = await fetch_saved_posts_page(
        db,
        user_id=user.id,
        cursor_saved_at=cursor_obj.sort_at,
        cursor_post_id=cursor_obj.post_id,
        limit=limit,
    )
    return _build_page(rows)


@router.get("/hidden", response_model=FeedPage)
async def list_hidden(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedPage:
    cursor_obj = PostListCursor.decode(cursor) if cursor else PostListCursor.initial()
    rows = await fetch_hidden_posts_page(
        db,
        user_id=user.id,
        cursor_hidden_at=cursor_obj.sort_at,
        cursor_post_id=cursor_obj.post_id,
        limit=limit,
    )
    return _build_page(rows)


@router.get("/read", response_model=FeedPage)
async def list_read(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedPage:
    cursor_obj = PostListCursor.decode(cursor) if cursor else PostListCursor.initial()
    rows = await fetch_read_posts_page(
        db,
        user_id=user.id,
        cursor_read_at=cursor_obj.sort_at,
        cursor_post_id=cursor_obj.post_id,
        limit=limit,
    )
    return _build_page(rows)


@router.post("/{post_id}/save", status_code=204)
async def save(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await _require_post(db, post_id)
    await save_post(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)


@router.delete("/{post_id}/save", status_code=204)
async def unsave(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await unsave_post(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/{post_id}/hide", status_code=204)
async def hide(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await _require_post(db, post_id)
    await hide_post_repo(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)


@router.delete("/{post_id}/hide", status_code=204)
async def unhide(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await unhide_post(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)
