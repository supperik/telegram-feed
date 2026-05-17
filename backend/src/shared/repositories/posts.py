from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Media, Post


async def upsert_post(
    session: AsyncSession,
    post_values: dict,
    media_values: list[dict],
) -> int | None:
    """Insert a post and its media rows. Returns the new post id, or None
    if the (channel_id, tg_message_id) pair already exists.

    Idempotent: callers can replay the same Telethon message safely.
    """
    stmt = (
        pg_insert(Post)
        .values(**post_values)
        .on_conflict_do_nothing(
            index_elements=[Post.channel_id, Post.tg_message_id]
        )
        .returning(Post.id)
    )
    res = await session.execute(stmt)
    new_id = res.scalar()
    if new_id is None:
        return None

    if media_values:
        await session.execute(
            insert(Media),
            [{**m, "post_id": new_id} for m in media_values],
        )
    return new_id
