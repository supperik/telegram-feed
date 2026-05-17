from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import User


async def upsert_user_by_tg_id(
    session: AsyncSession,
    *,
    tg_user_id: int,
    tg_username: str | None,
    tg_first_name: str | None,
    tg_photo_url: str | None,
) -> User:
    stmt = (
        pg_insert(User)
        .values(
            tg_user_id=tg_user_id,
            tg_username=tg_username,
            tg_first_name=tg_first_name,
            tg_photo_url=tg_photo_url,
        )
        .on_conflict_do_update(
            index_elements=[User.tg_user_id],
            set_={
                "tg_username": tg_username,
                "tg_first_name": tg_first_name,
                "tg_photo_url": tg_photo_url,
            },
        )
        .returning(User.id)
    )
    res = await session.execute(stmt)
    uid = res.scalar_one()
    fetched = await session.execute(
        select(User).where(User.id == uid),
        execution_options={"populate_existing": True},
    )
    return fetched.scalar_one()
