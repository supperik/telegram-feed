from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    Channel,
    ChannelSubscription,
    UserCatalogHiddenChannel,
    UserSource,
)
from shared.repositories.channels import decrement_ref_count, increment_ref_count


@dataclass(frozen=True)
class UserSourceRow:
    channel_id: int
    channel_username: str | None
    channel_title: str
    channel_photo_storage_key: str | None
    added_at: datetime
    subscription_status: str | None


async def add_user_source(
    session: AsyncSession, *, user_id: int, channel_id: int
) -> tuple[bool, str]:
    stmt = (
        pg_insert(UserSource)
        .values(user_id=user_id, channel_id=channel_id)
        .on_conflict_do_nothing(index_elements=[UserSource.user_id, UserSource.channel_id])
        .returning(UserSource.user_id)
    )
    res = await session.execute(stmt)
    was_new = res.scalar_one_or_none() is not None
    sub: ChannelSubscription | None = None
    if was_new:
        sub = await increment_ref_count(session, channel_id=channel_id)
    else:
        sub = await session.get(ChannelSubscription, channel_id)
    await session.execute(
        delete(UserCatalogHiddenChannel).where(
            UserCatalogHiddenChannel.user_id == user_id,
            UserCatalogHiddenChannel.channel_id == channel_id,
        )
    )
    return was_new, (sub.status if sub else "unknown")


async def remove_user_source(
    session: AsyncSession, *, user_id: int, channel_id: int
) -> bool:
    res = await session.execute(
        delete(UserSource)
        .where(UserSource.user_id == user_id, UserSource.channel_id == channel_id)
        .returning(UserSource.user_id)
    )
    removed = res.scalar_one_or_none() is not None
    if removed:
        await decrement_ref_count(session, channel_id=channel_id)
    return removed


async def list_user_sources(
    session: AsyncSession, *, user_id: int
) -> list[UserSourceRow]:
    stmt = (
        select(
            Channel.id,
            Channel.username,
            Channel.title,
            Channel.photo_storage_key,
            UserSource.added_at,
            ChannelSubscription.status,
        )
        .join(UserSource, UserSource.channel_id == Channel.id)
        .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id, isouter=True)
        .where(UserSource.user_id == user_id, Channel.banned.is_(False))
        .order_by(UserSource.added_at.desc())
    )
    res = await session.execute(stmt)
    return [UserSourceRow(*row) for row in res.all()]
