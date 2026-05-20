"""History-backfill state: eligibility query + per-channel lock primitives.

See docs/superpowers/specs/2026-05-20-history-backfill-design.md.
None of these functions commit — the caller owns the transaction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    Channel,
    ChannelBackfillState,
    ChannelSubscription,
    Post,
    UserReadPost,
    UserSource,
)


async def select_eligible_channels(
    session: AsyncSession, *, unread_threshold: int, limit: int
) -> list[tuple[int, int, int]]:
    """Channels eligible for history backfill.

    Eligible = actively subscribed, not banned, not fully backfilled, lock
    free, has >= 1 post, and has a following user with <= unread_threshold
    unread posts (read-watermark with prefetch buffer).

    Returns (channel_id, tg_chat_id, oldest_cursor), where oldest_cursor =
    COALESCE(stored cursor, MIN(Post.tg_message_id)) — the message id to
    fetch strictly below. ORDER BY last_backfill_at NULLS FIRST (round-robin).
    """
    # Per (user, channel): how many of the channel's posts the user has read.
    read_counts = (
        select(
            UserSource.user_id.label("user_id"),
            UserSource.channel_id.label("channel_id"),
            func.count(UserReadPost.post_id).label("read_n"),
        )
        .join(Post, Post.channel_id == UserSource.channel_id)
        .join(
            UserReadPost,
            and_(
                UserReadPost.post_id == Post.id,
                UserReadPost.user_id == UserSource.user_id,
            ),
        )
        .group_by(UserSource.user_id, UserSource.channel_id)
        .subquery()
    )

    has_follower = exists().where(UserSource.channel_id == Channel.id)

    # total_posts - max(read_n over followers) = min unread over followers.
    min_unread = func.count(func.distinct(Post.id)) - func.coalesce(
        func.max(read_counts.c.read_n), 0
    )

    stmt = (
        select(
            Channel.id,
            Channel.tg_chat_id,
            func.coalesce(
                ChannelBackfillState.oldest_seen_msg_id,
                func.min(Post.tg_message_id),
            ),
        )
        .join(Post, Post.channel_id == Channel.id)
        .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
        .outerjoin(
            ChannelBackfillState, ChannelBackfillState.channel_id == Channel.id
        )
        .outerjoin(read_counts, read_counts.c.channel_id == Channel.id)
        .where(Channel.banned.is_(False))
        .where(ChannelSubscription.status == "active")
        .where(
            or_(
                ChannelBackfillState.fully_backfilled.is_(None),
                ChannelBackfillState.fully_backfilled.is_(False),
            )
        )
        .where(
            or_(
                ChannelBackfillState.locked_until.is_(None),
                ChannelBackfillState.locked_until < func.now(),
            )
        )
        .where(has_follower)
        .group_by(
            Channel.id,
            Channel.tg_chat_id,
            ChannelBackfillState.oldest_seen_msg_id,
            ChannelBackfillState.last_backfill_at,
        )
        .having(min_unread <= unread_threshold)
        .order_by(ChannelBackfillState.last_backfill_at.asc().nulls_first())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return [(cid, chat, cursor) for cid, chat, cursor in res.all()]


async def try_acquire_lock(
    session: AsyncSession, *, channel_id: int, ttl_seconds: int
) -> bool:
    """Claim the channel for this tick. Creates the state row on first use.
    Returns True iff the lock was free (or absent) and is now held."""
    expiry = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl_seconds)
    stmt = (
        pg_insert(ChannelBackfillState)
        .values(channel_id=channel_id, locked_until=expiry)
        .on_conflict_do_update(
            index_elements=[ChannelBackfillState.channel_id],
            set_={"locked_until": expiry},
            where=or_(
                ChannelBackfillState.locked_until.is_(None),
                ChannelBackfillState.locked_until < func.now(),
            ),
        )
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def release_lock(
    session: AsyncSession, *, channel_id: int, oldest_seen_msg_id: int
) -> None:
    """End a backfill pass: clear the lock, advance the cursor, touch
    last_backfill_at (round-robin)."""
    await session.execute(
        update(ChannelBackfillState)
        .where(ChannelBackfillState.channel_id == channel_id)
        .values(
            locked_until=None,
            last_backfill_at=func.now(),
            oldest_seen_msg_id=oldest_seen_msg_id,
        )
    )


async def mark_fully_backfilled(
    session: AsyncSession, *, channel_id: int
) -> None:
    """Channel history exhausted — never pick it again."""
    await session.execute(
        update(ChannelBackfillState)
        .where(ChannelBackfillState.channel_id == channel_id)
        .values(fully_backfilled=True, locked_until=None, last_backfill_at=func.now())
    )


async def defer_after_flood_wait(
    session: AsyncSession, *, channel_id: int, seconds: int
) -> None:
    """On Telegram FloodWaitError: push the lock out so later ticks skip
    this channel until the wait elapses. Does not clear the lock."""
    until = datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)
    await session.execute(
        update(ChannelBackfillState)
        .where(ChannelBackfillState.channel_id == channel_id)
        .values(locked_until=until)
    )
