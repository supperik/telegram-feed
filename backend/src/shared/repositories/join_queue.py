from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import ChannelJoinQueue


async def pop_pending_join_request(session: AsyncSession) -> ChannelJoinQueue | None:
    """Atomically claim the oldest pending row by flipping it to in_progress.

    Uses SELECT ... FOR UPDATE SKIP LOCKED so multiple workers won't fight
    over the same row, even though MVP has a single ingester.
    Returns None if the queue has no pending rows.
    """
    stmt = (
        select(ChannelJoinQueue)
        .where(ChannelJoinQueue.status == "pending")
        .order_by(ChannelJoinQueue.created_at.asc(), ChannelJoinQueue.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    res = await session.execute(stmt)
    row = res.scalar_one_or_none()
    if row is None:
        return None
    row.status = "in_progress"
    row.updated_at = datetime.now(tz=timezone.utc)
    return row


async def find_active_public_request(
    session: AsyncSession,
    *,
    username: str,
    requested_by_user_id: int,
) -> ChannelJoinQueue | None:
    """Return this user's in-flight (pending / in_progress) public-username
    join request for `username`, or None.

    Used to dedup repeat re-subscribe taps: a second POST while the first
    join is still queued reuses that row. Scoped per user — a different
    user re-subscribing to the same channel still gets their own request,
    so their user_source link is created when the join completes.
    """
    res = await session.execute(
        select(ChannelJoinQueue)
        .where(
            ChannelJoinQueue.kind == "public_username",
            ChannelJoinQueue.channel_username == username,
            ChannelJoinQueue.requested_by_user_id == requested_by_user_id,
            ChannelJoinQueue.status.in_(("pending", "in_progress")),
        )
        .order_by(ChannelJoinQueue.id.asc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def mark_join_done(
    session: AsyncSession, *, queue_id: int, channel_id: int
) -> None:
    await session.execute(
        update(ChannelJoinQueue)
        .where(ChannelJoinQueue.id == queue_id)
        .values(status="done", channel_id=channel_id, updated_at=datetime.now(tz=timezone.utc))
    )


async def mark_join_failed(
    session: AsyncSession,
    *,
    queue_id: int,
    error_code: str,
    error_reason: str | None = None,
) -> None:
    """Mark a queue row as failed.

    `error_code` is a stable enum-like string consumed by the UI (e.g.
    `username_not_occupied`, `invite_invalid`, `flood_wait`, `unknown`).
    `error_reason` is free-form debug text (typically the exception
    class name or repr) kept for operators/logs.
    """
    await session.execute(
        update(ChannelJoinQueue)
        .where(ChannelJoinQueue.id == queue_id)
        .values(
            status="failed",
            error_code=error_code,
            error_reason=error_reason,
            updated_at=datetime.now(tz=timezone.utc),
        )
    )


async def mark_pending_approval(session: AsyncSession, *, queue_id: int) -> None:
    """Park a private-invite row pending owner approval.

    Used when ImportChatInviteRequest reports the invite was placed into
    the channel's join-request queue rather than auto-accepted. A separate
    reaper turns these into `done` once the user actually joins.
    """
    await session.execute(
        update(ChannelJoinQueue)
        .where(ChannelJoinQueue.id == queue_id)
        .values(status="pending_approval", updated_at=datetime.now(tz=timezone.utc))
    )


async def fetch_pending_approval(session: AsyncSession) -> list[ChannelJoinQueue]:
    """Return every queue row currently in `pending_approval` status."""
    res = await session.execute(
        select(ChannelJoinQueue).where(ChannelJoinQueue.status == "pending_approval")
    )
    return list(res.scalars().all())
