"""Periodic sweep: leave channels with no subscribers."""
import asyncio

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from telethon import TelegramClient
from telethon.tl.functions.channels import LeaveChannelRequest

from shared.models import Channel, ChannelSubscription

log = structlog.get_logger(__name__)


async def run_refcount_sweep(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_s: float = 300.0,
) -> None:
    log.info("refcount_sweep.started", interval_s=interval_s)
    while True:
        try:
            await _sweep_once(client, session_factory)
        except Exception as e:  # noqa: BLE001
            try:
                log.exception("refcount_sweep.error", error=str(e))
            except ValueError:
                pass
        await asyncio.sleep(interval_s)


async def _sweep_once(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
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
        try:
            entity = await client.get_entity(tg_chat_id)
            await client(LeaveChannelRequest(entity))
        except Exception as e:  # noqa: BLE001
            try:
                log.warning("refcount_sweep.leave_failed",
                            channel_id=channel_id, error=str(e))
            except ValueError:
                pass
            continue

        async with session_factory() as session:
            await session.execute(
                update(ChannelSubscription)
                .where(ChannelSubscription.channel_id == channel_id)
                .values(status="left")
            )
            await session.commit()
        try:
            log.info("refcount_sweep.left", channel_id=channel_id)
        except ValueError:
            pass
