import base64
import json
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Channel, ChannelSubscription, Post


MAX_CHANNELS_LIMIT = 200


def _encode_cursor(banned: bool, last_post_at: datetime | None, channel_id: int) -> str:
    payload = {
        "b": int(banned),
        "lp": last_post_at.isoformat() if last_post_at else None,
        "id": channel_id,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[bool, datetime | None, int]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    last_post_at = datetime.fromisoformat(payload["lp"]) if payload["lp"] else None
    return bool(payload["b"]), last_post_at, int(payload["id"])


def _admin_channel_select() -> tuple[Select, Any, Any]:
    """SELECT used by both list and single-channel admin views.

    Returns the base statement plus the labelled (last_post_at, posts_count)
    columns so callers can reuse them for ORDER BY / WHERE without rebuilding
    the aggregate subquery.
    """
    posts_agg = (
        select(
            Post.channel_id.label("channel_id"),
            func.count(Post.id).label("posts_count"),
            func.max(Post.posted_at).label("last_post_at"),
        )
        .group_by(Post.channel_id)
        .subquery()
    )
    last_post_col = posts_agg.c.last_post_at
    posts_count_col = func.coalesce(posts_agg.c.posts_count, 0)

    stmt = (
        select(
            Channel.id,
            Channel.tg_chat_id,
            Channel.username,
            Channel.title,
            Channel.description,
            Channel.photo_storage_key,
            posts_count_col.label("posts_count"),
            Channel.banned,
            Channel.banned_reason,
            last_post_col.label("last_post_at"),
            Channel.created_at,
            func.coalesce(ChannelSubscription.ref_count, 0).label("ref_count"),
        )
        .select_from(Channel)
        .outerjoin(posts_agg, posts_agg.c.channel_id == Channel.id)
        .outerjoin(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
    )
    return stmt, last_post_col, posts_count_col


async def list_channels_for_admin(
    session: AsyncSession,
    *,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[dict[str, Any]], str | None]:
    """Paginated channel list with metrics. Sort: banned DESC, last_post_at DESC NULLS LAST, id DESC.

    posts_count and last_post_at are computed live from the posts table
    (the matching columns on `channels` are not maintained).
    """
    limit = max(1, min(MAX_CHANNELS_LIMIT, limit))
    stmt, last_post_col, _ = _admin_channel_select()
    stmt = stmt.order_by(
        Channel.banned.desc(),
        last_post_col.desc().nulls_last(),
        Channel.id.desc(),
    ).limit(limit + 1)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Channel.username.ilike(pattern),
                Channel.title.ilike(pattern),
            )
        )

    if cursor:
        c_banned, c_lp, c_id = _decode_cursor(cursor)
        # Compose "row < cursor" under (banned DESC, last_post_at DESC NULLS LAST, id DESC).
        less_banned = Channel.banned < c_banned
        if c_lp is None:
            # Cursor row has NULL lp (which sorts last under DESC NULLS LAST).
            # Below it within same banned bucket: lp is null AND id < c_id.
            same_or_less = and_(
                Channel.banned == c_banned,
                last_post_col.is_(None),
                Channel.id < c_id,
            )
            stmt = stmt.where(or_(less_banned, same_or_less))
        else:
            same_banned_less_lp = and_(
                Channel.banned == c_banned,
                or_(
                    last_post_col < c_lp,
                    last_post_col.is_(None),
                ),
            )
            same_banned_same_lp_less_id = and_(
                Channel.banned == c_banned,
                last_post_col == c_lp,
                Channel.id < c_id,
            )
            stmt = stmt.where(
                or_(less_banned, same_banned_less_lp, same_banned_same_lp_less_id)
            )

    res = await session.execute(stmt)
    rows = list(res.mappings().all())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last["banned"], last["last_post_at"], last["id"])

    return [dict(r) for r in rows], next_cursor


async def get_channel_row_for_admin(
    session: AsyncSession, channel_id: int
) -> dict[str, Any] | None:
    """Single-channel variant of list_channels_for_admin: same shape (incl.
    aggregated posts_count / last_post_at / ref_count), filtered by id."""
    stmt, _, _ = _admin_channel_select()
    stmt = stmt.where(Channel.id == channel_id)
    res = await session.execute(stmt)
    row = res.mappings().first()
    return dict(row) if row else None


async def get_channel_or_none(session: AsyncSession, channel_id: int) -> Channel | None:
    res = await session.execute(select(Channel).where(Channel.id == channel_id))
    return res.scalar_one_or_none()


async def ban_channel(session: AsyncSession, channel_id: int, reason: str) -> Channel | None:
    res = await session.execute(
        update(Channel)
        .where(Channel.id == channel_id)
        .values(banned=True, banned_reason=reason)
        .returning(Channel)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()


async def unban_channel(session: AsyncSession, channel_id: int) -> Channel | None:
    res = await session.execute(
        update(Channel)
        .where(Channel.id == channel_id)
        .values(banned=False, banned_reason=None)
        .returning(Channel)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()
