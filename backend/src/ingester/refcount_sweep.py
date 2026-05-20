"""Periodic sweep: park channels with no subscribers as dormant.

A channel with ref_count==0 keeps the userbot as a member — the sweep only
flips the subscription to `dormant` and drops it from the live chat_map so
the ingester stops reading it. Re-subscription reactivates the channel
through the join queue (telegram-feed-iy7).
"""
import asyncio

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ingester.live import _to_marked_chat_id
from shared.models import Channel, ChannelSubscription

log = structlog.get_logger(__name__)


async def run_refcount_sweep(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_s: float = 300.0,
    chat_map: dict[int, int] | None = None,
) -> None:
    log.info("refcount_sweep.started", interval_s=interval_s)
    while True:
        try:
            await _sweep_once(session_factory, chat_map=chat_map)
        except Exception as e:  # noqa: BLE001
            log.exception("refcount_sweep.error", error=str(e))
        await asyncio.sleep(interval_s)


async def _sweep_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    chat_map: dict[int, int] | None = None,
) -> None:
    async with session_factory() as session:
        res = await session.execute(
            select(Channel.id, Channel.tg_chat_id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(ChannelSubscription.ref_count == 0)
            .where(ChannelSubscription.status == "active")
        )
        targets = list(res.all())

    for channel_id, tg_chat_id in targets:
        async with session_factory() as session:
            await session.execute(
                update(ChannelSubscription)
                .where(ChannelSubscription.channel_id == channel_id)
                .values(status="dormant")
            )
            await session.commit()
        # Drop from the live chat_map so the NewMessage handler stops routing
        # this channel's events at once, without waiting for a restart.
        if chat_map is not None:
            chat_map.pop(_to_marked_chat_id(tg_chat_id), None)
        log.info("refcount_sweep.dormant", channel_id=channel_id)
