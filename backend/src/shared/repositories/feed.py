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
    UserReadPost,
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
    video_storage_key: str | None = None


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
    channel_tg_chat_id: int
    channel_username: str | None
    channel_title: str
    channel_photo_storage_key: str | None
    channel_invite_hash: str | None
    is_saved: bool
    # Populated by fetch_saved_posts_page / fetch_hidden_posts_page /
    # fetch_read_posts_page — the saved_at / hidden_at / read_at value used as
    # the keyset sort key. None for the main feed (which sorts by posted_at
    # and uses that directly).
    sort_at: datetime | None = None
    media: list[FeedMediaRow] = field(default_factory=list)


def _post_and_channel_columns():
    return (
        Post.id,
        Post.tg_message_id,
        Post.posted_at,
        Post.text,
        Post.text_html,
        Post.views,
        Post.forwards,
        Channel.id.label("channel_id"),
        Channel.tg_chat_id.label("channel_tg_chat_id"),
        Channel.username,
        Channel.title,
        Channel.photo_storage_key,
        Channel.invite_hash,
    )


def _row_to_feed_post(r, *, is_saved: bool, sort_at: datetime | None = None) -> FeedPostRow:
    return FeedPostRow(
        post_id=r.id,
        tg_message_id=r.tg_message_id,
        posted_at=r.posted_at,
        text=r.text,
        text_html=r.text_html,
        views=r.views,
        forwards=r.forwards,
        channel_id=r.channel_id,
        channel_tg_chat_id=r.channel_tg_chat_id,
        channel_username=r.username,
        channel_title=r.title,
        channel_photo_storage_key=r.photo_storage_key,
        channel_invite_hash=r.invite_hash,
        is_saved=is_saved,
        sort_at=sort_at,
    )


async def _attach_media(session: AsyncSession, rows: list[FeedPostRow]) -> None:
    if not rows:
        return
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
                Media.video_storage_key,
            )
            .where(Media.post_id.in_([r.post_id for r in rows]))
            .order_by(Media.post_id, Media.position)
        )
    ).all()
    by_post: dict[int, list[FeedMediaRow]] = {}
    for m in media_rows:
        by_post.setdefault(m.post_id, []).append(
            FeedMediaRow(
                id=m.id,
                type=m.type,
                width=m.width,
                height=m.height,
                duration=m.duration,
                video_storage_key=m.video_storage_key,
            )
        )
    for r in rows:
        r.media = by_post.get(r.post_id, [])


async def fetch_feed_page(
    session: AsyncSession,
    *,
    user_id: int,
    cursor_posted_at: datetime,
    cursor_post_id: int,
    limit: int,
    include_read: bool = False,
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
    read_post_q = exists().where(
        and_(UserReadPost.user_id == user_id, UserReadPost.post_id == Post.id)
    )

    conditions = [
        Channel.banned.is_(False),
        ~hidden_post_q,
        ~hidden_channel_q,
        tuple_(Post.posted_at, Post.id) < tuple_(cursor_posted_at, cursor_post_id),
    ]
    if not include_read:
        conditions.append(~read_post_q)

    stmt = (
        select(*_post_and_channel_columns(), saved_q.label("is_saved"))
        .join(Channel, Channel.id == Post.channel_id)
        .join(
            UserSource,
            and_(UserSource.channel_id == Post.channel_id, UserSource.user_id == user_id),
        )
        .where(*conditions)
        .order_by(Post.posted_at.desc(), Post.id.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = [_row_to_feed_post(r, is_saved=bool(r.is_saved)) for r in res.all()]
    await _attach_media(session, rows)
    return rows


async def fetch_saved_posts_page(
    session: AsyncSession,
    *,
    user_id: int,
    cursor_saved_at: datetime,
    cursor_post_id: int,
    limit: int,
) -> list[FeedPostRow]:
    stmt = (
        select(*_post_and_channel_columns(), UserSavedPost.saved_at.label("sort_at"))
        .join(Channel, Channel.id == Post.channel_id)
        .join(
            UserSavedPost,
            and_(UserSavedPost.post_id == Post.id, UserSavedPost.user_id == user_id),
        )
        .where(
            Channel.banned.is_(False),
            tuple_(UserSavedPost.saved_at, Post.id)
            < tuple_(cursor_saved_at, cursor_post_id),
        )
        .order_by(UserSavedPost.saved_at.desc(), Post.id.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = [_row_to_feed_post(r, is_saved=True, sort_at=r.sort_at) for r in res.all()]
    await _attach_media(session, rows)
    return rows


async def fetch_hidden_posts_page(
    session: AsyncSession,
    *,
    user_id: int,
    cursor_hidden_at: datetime,
    cursor_post_id: int,
    limit: int,
) -> list[FeedPostRow]:
    saved_q = exists().where(
        and_(UserSavedPost.user_id == user_id, UserSavedPost.post_id == Post.id)
    )
    stmt = (
        select(
            *_post_and_channel_columns(),
            saved_q.label("is_saved"),
            UserHiddenPost.hidden_at.label("sort_at"),
        )
        .join(Channel, Channel.id == Post.channel_id)
        .join(
            UserHiddenPost,
            and_(UserHiddenPost.post_id == Post.id, UserHiddenPost.user_id == user_id),
        )
        .where(
            Channel.banned.is_(False),
            tuple_(UserHiddenPost.hidden_at, Post.id)
            < tuple_(cursor_hidden_at, cursor_post_id),
        )
        .order_by(UserHiddenPost.hidden_at.desc(), Post.id.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = [
        _row_to_feed_post(r, is_saved=bool(r.is_saved), sort_at=r.sort_at)
        for r in res.all()
    ]
    await _attach_media(session, rows)
    return rows


async def fetch_read_posts_page(
    session: AsyncSession,
    *,
    user_id: int,
    cursor_read_at: datetime,
    cursor_post_id: int,
    limit: int,
) -> list[FeedPostRow]:
    saved_q = exists().where(
        and_(UserSavedPost.user_id == user_id, UserSavedPost.post_id == Post.id)
    )
    stmt = (
        select(
            *_post_and_channel_columns(),
            saved_q.label("is_saved"),
            UserReadPost.read_at.label("sort_at"),
        )
        .join(Channel, Channel.id == Post.channel_id)
        .join(
            UserReadPost,
            and_(UserReadPost.post_id == Post.id, UserReadPost.user_id == user_id),
        )
        .where(
            Channel.banned.is_(False),
            tuple_(UserReadPost.read_at, Post.id)
            < tuple_(cursor_read_at, cursor_post_id),
        )
        .order_by(UserReadPost.read_at.desc(), Post.id.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    rows = [
        _row_to_feed_post(r, is_saved=bool(r.is_saved), sort_at=r.sort_at)
        for r in res.all()
    ]
    await _attach_media(session, rows)
    return rows
