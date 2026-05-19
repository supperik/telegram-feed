"""One-shot backfill: download and cache the profile photo of every
active channel whose `photo_storage_key` is still NULL.

Idempotent: once every active channel either has a stored key or has
been determined to have no avatar (and gets skipped on subsequent
passes because we don't write empty values), the targets query may
keep returning channels without keys. To avoid hot-looping forever on
channels that genuinely have no avatar, callers should run this on
boot only — not on every refcount sweep.

Designed to be wired into `ingester.main` boot after `merge_existing_
albums`. Failures per channel are swallowed so a single PeerUser /
network flake does not break the whole pass.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from minio import Minio

from ingester.photos import download_and_store_channel_photo
from shared.models import Channel, ChannelSubscription

log = structlog.get_logger(__name__)

Downloader = Callable[..., Awaitable[str | None]]


async def backfill_channel_photos(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    bucket: str,
    downloader: Downloader | None = None,
) -> int:
    """Download missing channel avatars for active subscriptions.

    Returns the count of channels whose `photo_storage_key` was set
    during this pass.
    """
    download_fn: Downloader = downloader or download_and_store_channel_photo

    async with session_factory() as session:
        res = await session.execute(
            select(Channel.id, Channel.tg_chat_id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(
                Channel.photo_storage_key.is_(None),
                ChannelSubscription.status == "active",
            )
        )
        rows = res.all()

    if not rows:
        log.info("backfill_channel_photos.noop")
        return 0

    log.info("backfill_channel_photos.start", channels=len(rows))

    filled = 0
    for channel_id, tg_chat_id in rows:
        try:
            # PeerChannel for unambiguous resolution after a cold restart; see 7h6.
            entity = await client.get_entity(PeerChannel(tg_chat_id))
        except Exception as e:  # noqa: BLE001
            log.warning(
                "backfill_channel_photos.get_entity_failed",
                channel_id=channel_id,
                error=str(e),
            )
            continue

        try:
            storage_key = await download_fn(
                client, minio_client, entity,
                channel_id=channel_id, bucket=bucket,
            )
        except Exception as e:  # noqa: BLE001
            log.warning(
                "backfill_channel_photos.download_failed",
                channel_id=channel_id,
                error=str(e),
            )
            continue

        if storage_key is None:
            continue

        async with session_factory() as session:
            await session.execute(
                update(Channel)
                .where(Channel.id == channel_id)
                .values(photo_storage_key=storage_key)
            )
            await session.commit()
        filled += 1

    log.info("backfill_channel_photos.complete", filled=filled)
    return filled
