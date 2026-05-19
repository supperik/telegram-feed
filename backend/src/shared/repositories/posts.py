from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Media, Post


async def upsert_post(
    session: AsyncSession,
    post_values: dict,
    media_values: list[dict],
) -> int | None:
    """Insert a post and its media rows. Returns the Post id (new or
    existing) on success, or None if the (channel_id, tg_message_id)
    pair already exists and there is no group to append to.

    Behaviour:
    - When ``post_values["tg_grouped_id"]`` is None (single message),
      the row is inserted with ON CONFLICT (channel_id, tg_message_id)
      DO NOTHING. Returns new id, or None on conflict.
    - When ``tg_grouped_id`` is set (media group), any existing Post in
      the same channel with the same group id is reused: ``media_values``
      are appended with positions continuing past ``MAX(position)`` of
      the existing post. Returns the existing Post id. No new Post row.
    - Idempotent: replaying the same Telethon message is safe in both
      modes (the ON CONFLICT or the SELECT prevents duplicates).
    """
    grouped_id = post_values.get("tg_grouped_id")

    if grouped_id is not None:
        existing_res = await session.execute(
            select(Post.id).where(
                Post.channel_id == post_values["channel_id"],
                Post.tg_grouped_id == grouped_id,
            )
        )
        existing_id = existing_res.scalar_one_or_none()
        if existing_id is not None:
            if not media_values:
                return existing_id
            # Dedupe by tg_file_id: catchup_channels re-feeds the album's
            # tail messages (msg_id > head.id) on every restart, so the
            # same media would otherwise be appended again each boot.
            present_res = await session.execute(
                select(Media.tg_file_id).where(Media.post_id == existing_id)
            )
            present = set(present_res.scalars().all())
            new_media = [m for m in media_values if m["tg_file_id"] not in present]
            if not new_media:
                return existing_id
            max_pos_res = await session.execute(
                select(func.coalesce(func.max(Media.position), -1)).where(
                    Media.post_id == existing_id
                )
            )
            max_pos = max_pos_res.scalar_one()
            await session.execute(
                insert(Media),
                [
                    {**m, "post_id": existing_id, "position": max_pos + 1 + idx}
                    for idx, m in enumerate(new_media)
                ],
            )
            return existing_id

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
