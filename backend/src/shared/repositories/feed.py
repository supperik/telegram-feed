from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, exists, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    Channel,
    Media,
    Post,
    UserHiddenChannel,
    UserHiddenPost,
    UserSavedPost,
    UserSource,
)


@dataclass
class FeedMediaRow:
    id: int
    type: str
    width: int | None
    height: int | None
    duration: int | None


@dataclass
class FeedPostRow:
    post_id: int
    tg_message_id: int
    posted_at: datetime
    text: str | None
    text_html: str | None
    views: int | None
    forwards: int | None
    channel_id: int
    channel_username: str | None
    channel_title: str
    channel_photo_storage_key: str | None
    is_saved: bool
    media: list[FeedMediaRow] = field(default_factory=list)


async def fetch_feed_page(
    session: AsyncSession,
    *,
    user_id: int,
    cursor_posted_at: datetime,
    cursor_post_id: int,
    limit: int,
) -> list[FeedPostRow]:
    saved_q = exists().where(
        and_(UserSavedPost.user_id == user_id, UserSavedPost.post_id == Post.id)
    )
    hidden_post_q = exists().where(
        and_(UserHiddenPost.user_id == user_id, UserHiddenPost.post_id == Post.id)
    )
    hidden_channel_q = exists().where(
        and_(
            UserHiddenChannel.user_id == user_id,
            UserHiddenChannel.channel_id == Post.channel_id,
        )
    )

    stmt = (
        select(
            Post.id,
            Post.tg_message_id,
            Post.posted_at,
            Post.text,
            Post.text_html,
            Post.views,
            Post.forwards,
            Channel.id.label("channel_id"),
            Channel.username,
            Channel.title,
            Channel.photo_storage_key,
            saved_q.label("is_saved"),
        )
        .join(Channel, Channel.id == Post.channel_id)
        .join(
            UserSource,
            and_(UserSource.channel_id == Post.channel_id, UserSource.user_id == user_id),
        )
        .where(
            Channel.banned.is_(False),
            ~hidden_post_q,
            ~hidden_channel_q,
            tuple_(Post.posted_at, Post.id) < tuple_(cursor_posted_at, cursor_post_id),
        )
        .order_by(Post.posted_at.desc(), Post.id.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = [
        FeedPostRow(
            post_id=r.id,
            tg_message_id=r.tg_message_id,
            posted_at=r.posted_at,
            text=r.text,
            text_html=r.text_html,
            views=r.views,
            forwards=r.forwards,
            channel_id=r.channel_id,
            channel_username=r.username,
            channel_title=r.title,
            channel_photo_storage_key=r.photo_storage_key,
            is_saved=bool(r.is_saved),
        )
        for r in res.all()
    ]
    if not rows:
        return rows
    media_rows = (
        await session.execute(
            select(
                Media.id,
                Media.post_id,
                Media.type,
                Media.width,
                Media.height,
                Media.duration,
                Media.position,
            )
            .where(Media.post_id.in_([r.post_id for r in rows]))
            .order_by(Media.post_id, Media.position)
        )
    ).all()
    by_post: dict[int, list[FeedMediaRow]] = {}
    for m in media_rows:
        by_post.setdefault(m.post_id, []).append(
            FeedMediaRow(
                id=m.id, type=m.type, width=m.width, height=m.height, duration=m.duration
            )
        )
    for r in rows:
        r.media = by_post.get(r.post_id, [])
    return rows
