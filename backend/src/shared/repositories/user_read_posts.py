from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import UserReadPost


async def bulk_mark_read(
    session: AsyncSession, *, user_id: int, post_ids: list[int]
) -> int:
    """Mark posts read for a user. Idempotent — re-marking returns 0.

    Returns the count of rows actually inserted (ids not already read).
    Does not validate that the user could see the posts.
    """
    unique_ids = list(dict.fromkeys(post_ids))
    if not unique_ids:
        return 0
    stmt = (
        pg_insert(UserReadPost)
        .values([{"user_id": user_id, "post_id": pid} for pid in unique_ids])
        .on_conflict_do_nothing(
            index_elements=[UserReadPost.user_id, UserReadPost.post_id]
        )
    )
    result = await session.execute(stmt)
    return result.rowcount
