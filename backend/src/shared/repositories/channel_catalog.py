from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, exists, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from api.pagination import CatalogCursor
from shared.models import (
    Channel,
    ChannelSubscription,
    UserCatalogHiddenChannel,
    UserSource,
)


@dataclass(frozen=True)
class CatalogRow:
    channel_id: int
    username: str | None
    title: str
    photo_storage_key: str | None
    posts_count: int
    last_post_at: datetime | None
    subscribers_count: int
    is_subscribed: bool
    is_hidden_from_catalog: bool
    hidden_at: datetime | None = None  # only populated in view=hidden, reserved for Task 4


def _q_filter(q: str | None):
    if not q:
        return None
    # ILIKE %q% — escape SQL wildcards in q so the user can search literally.
    needle = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return or_(
        Channel.title.ilike(needle, escape="\\"),
        Channel.username.ilike(needle, escape="\\"),
    )


async def list_catalog_available(
    session: AsyncSession,
    *,
    user_id: int,
    cursor: CatalogCursor,
    limit: int,
    q: str | None,
) -> list[CatalogRow]:
    assert cursor.view == "available"
    hidden_subq = (
        select(UserCatalogHiddenChannel.channel_id)
        .where(UserCatalogHiddenChannel.user_id == user_id)
        .subquery()
    )
    is_sub = exists().where(
        and_(UserSource.user_id == user_id, UserSource.channel_id == Channel.id)
    )

    stmt = (
        select(
            Channel.id.label("channel_id"),
            Channel.username,
            Channel.title,
            Channel.photo_storage_key,
            Channel.posts_count,
            Channel.last_post_at,
            ChannelSubscription.ref_count.label("subscribers_count"),
            is_sub.label("is_subscribed"),
        )
        .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
        .where(
            Channel.banned.is_(False),
            ChannelSubscription.status == "active",
            ChannelSubscription.ref_count > 0,
            Channel.id.notin_(select(hidden_subq.c.channel_id)),
            tuple_(Channel.posts_count, Channel.id)
            < tuple_(cursor.posts_count, cursor.channel_id),
        )
        .order_by(Channel.posts_count.desc(), Channel.id.desc())
        .limit(limit)
    )
    q_filter = _q_filter(q)
    if q_filter is not None:
        stmt = stmt.where(q_filter)

    res = await session.execute(stmt)
    return [
        CatalogRow(
            channel_id=r.channel_id,
            username=r.username,
            title=r.title,
            photo_storage_key=r.photo_storage_key,
            posts_count=r.posts_count,
            last_post_at=r.last_post_at,
            subscribers_count=r.subscribers_count,
            is_subscribed=bool(r.is_subscribed),
            is_hidden_from_catalog=False,
            hidden_at=None,
        )
        for r in res.all()
    ]
