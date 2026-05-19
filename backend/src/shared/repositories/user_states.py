from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    Channel,
    UserHiddenChannel,
    UserHiddenPost,
    UserSavedPost,
    UserSource,
)


async def save_post(session: AsyncSession, *, user_id: int, post_id: int) -> None:
    await session.execute(
        pg_insert(UserSavedPost)
        .values(user_id=user_id, post_id=post_id)
        .on_conflict_do_nothing(index_elements=[UserSavedPost.user_id, UserSavedPost.post_id])
    )


async def unsave_post(session: AsyncSession, *, user_id: int, post_id: int) -> None:
    await session.execute(
        delete(UserSavedPost).where(
            UserSavedPost.user_id == user_id, UserSavedPost.post_id == post_id
        )
    )


async def hide_post(session: AsyncSession, *, user_id: int, post_id: int) -> None:
    await session.execute(
        pg_insert(UserHiddenPost)
        .values(user_id=user_id, post_id=post_id)
        .on_conflict_do_nothing(index_elements=[UserHiddenPost.user_id, UserHiddenPost.post_id])
    )


async def unhide_post(session: AsyncSession, *, user_id: int, post_id: int) -> None:
    await session.execute(
        delete(UserHiddenPost).where(
            UserHiddenPost.user_id == user_id, UserHiddenPost.post_id == post_id
        )
    )


async def hide_channel(session: AsyncSession, *, user_id: int, channel_id: int) -> None:
    await session.execute(
        pg_insert(UserHiddenChannel)
        .values(user_id=user_id, channel_id=channel_id)
        .on_conflict_do_nothing(
            index_elements=[UserHiddenChannel.user_id, UserHiddenChannel.channel_id]
        )
    )


async def unhide_channel(session: AsyncSession, *, user_id: int, channel_id: int) -> None:
    await session.execute(
        delete(UserHiddenChannel).where(
            UserHiddenChannel.user_id == user_id,
            UserHiddenChannel.channel_id == channel_id,
        )
    )


@dataclass(frozen=True)
class HiddenChannelRow:
    channel_id: int
    channel_username: str | None
    channel_title: str
    channel_photo_storage_key: str | None
    hidden_at: datetime


async def list_hidden_channels(
    session: AsyncSession, *, user_id: int
) -> list[HiddenChannelRow]:
    stmt = (
        select(
            Channel.id,
            Channel.username,
            Channel.title,
            Channel.photo_storage_key,
            UserHiddenChannel.hidden_at,
        )
        .join(UserHiddenChannel, UserHiddenChannel.channel_id == Channel.id)
        .join(
            UserSource,
            (UserSource.channel_id == Channel.id)
            & (UserSource.user_id == UserHiddenChannel.user_id),
        )
        .where(UserHiddenChannel.user_id == user_id, Channel.banned.is_(False))
        .order_by(UserHiddenChannel.hidden_at.desc(), Channel.id.desc())
    )
    res = await session.execute(stmt)
    return [HiddenChannelRow(*row) for row in res.all()]
