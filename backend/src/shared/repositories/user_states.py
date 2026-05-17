from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import UserHiddenChannel, UserHiddenPost, UserSavedPost


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


async def hide_channel(session: AsyncSession, *, user_id: int, channel_id: int) -> None:
    await session.execute(
        pg_insert(UserHiddenChannel)
        .values(user_id=user_id, channel_id=channel_id)
        .on_conflict_do_nothing(
            index_elements=[UserHiddenChannel.user_id, UserHiddenChannel.channel_id]
        )
    )
