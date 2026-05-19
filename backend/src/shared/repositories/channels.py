from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Channel, ChannelSubscription


async def upsert_channel(
    session: AsyncSession,
    *,
    tg_chat_id: int,
    username: str | None,
    title: str,
    description: str | None = None,
    photo_storage_key: str | None = None,
) -> Channel:
    """Insert a channel if absent, else return the existing row unchanged.

    Idempotent on (tg_chat_id). Does NOT update existing rows — callers that
    want to refresh title/photo should issue a separate UPDATE.
    """
    stmt = (
        pg_insert(Channel)
        .values(
            tg_chat_id=tg_chat_id,
            username=username,
            title=title,
            description=description,
            photo_storage_key=photo_storage_key,
        )
        .on_conflict_do_nothing(index_elements=[Channel.tg_chat_id])
        .returning(Channel.id)
    )
    res = await session.execute(stmt)
    inserted_id = res.scalar()
    if inserted_id is None:
        # Existed already; fetch it.
        existing = await session.execute(
            select(Channel).where(Channel.tg_chat_id == tg_chat_id)
        )
        return existing.scalar_one()
    return (
        await session.execute(select(Channel).where(Channel.id == inserted_id))
    ).scalar_one()


async def get_subscription(session: AsyncSession, *, channel_id: int) -> ChannelSubscription | None:
    res = await session.execute(
        select(ChannelSubscription).where(ChannelSubscription.channel_id == channel_id)
    )
    return res.scalar_one_or_none()


async def increment_ref_count(
    session: AsyncSession, *, channel_id: int
) -> ChannelSubscription:
    """Atomic increment of ref_count. Creates the subscription row if missing,
    with status='pending_backfill' and ref_count=1."""
    stmt = (
        pg_insert(ChannelSubscription)
        .values(channel_id=channel_id, status="pending_backfill", ref_count=1)
        .on_conflict_do_update(
            index_elements=[ChannelSubscription.channel_id],
            set_={"ref_count": ChannelSubscription.ref_count + 1},
        )
        .returning(ChannelSubscription)
    )
    res = await session.execute(
        stmt, execution_options={"populate_existing": True}
    )
    return res.scalar_one()


async def decrement_ref_count(
    session: AsyncSession, *, channel_id: int
) -> ChannelSubscription | None:
    """Atomic decrement, clamped at 0. Returns the updated row or None if no
    subscription row exists yet."""
    stmt = (
        update(ChannelSubscription)
        .where(ChannelSubscription.channel_id == channel_id)
        .values(
            ref_count=func_max_zero(ChannelSubscription.ref_count - 1)
        )
        .returning(ChannelSubscription)
    )
    res = await session.execute(
        stmt, execution_options={"populate_existing": True}
    )
    return res.scalar_one_or_none()


def func_max_zero(expr):
    """SQL: GREATEST(expr, 0). Helper to express the clamp inline."""
    from sqlalchemy import func, literal
    return func.greatest(expr, literal(0))
