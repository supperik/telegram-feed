"""One-shot backfill: re-fetch the last N messages for every channel that
still has Media rows with storage_key=NULL, and download the missing files.

Designed as a self-healing pass:
- Targets query selects only channels with `Media.storage_key IS NULL` AND
  `ChannelSubscription.status == 'active'`. After the first successful run
  this returns nothing, so subsequent boots skip Telethon entirely.
- Per channel: iter_messages(limit=N) (no `min_id`), match each yielded
  message to a Post in our DB, find Media rows with storage_key=NULL, and
  delegate to `download_and_set_storage_keys` (the same helper used by
  on_new_message and catchup_channels).

Called from `ingester.main.main()` after catchup, before subscribe.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from telethon import TelegramClient
from minio import Minio

from ingester.live import download_and_set_storage_keys
from shared.models import Channel, ChannelSubscription, Media, Post

log = structlog.get_logger(__name__)


async def backfill_recent_media(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    bucket: str,
    settings: Any,
    limit: int = 50,
) -> int:
    """Walk the last `limit` messages of every active channel that has at
    least one Media row with storage_key=NULL, download the missing
    photos/video thumbs, and set the storage_key. Idempotent.

    Returns the number of media rows whose storage_key was filled in.
    """
    async with session_factory() as session:
        res = await session.execute(
            select(Channel.id, Channel.tg_chat_id)
            .select_from(Media)
            .join(Post, Post.id == Media.post_id)
            .join(Channel, Channel.id == Post.channel_id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(
                Media.storage_key.is_(None),
                ChannelSubscription.status == "active",
            )
            .distinct()
        )
        targets = res.all()

    if not targets:
        log.info("backfill.noop")
        return 0

    log.info("backfill.start", channels=len(targets), limit=limit)

    total = 0
    for channel_id, tg_chat_id in targets:
        try:
            entity = await client.get_entity(tg_chat_id)
        except Exception as e:  # noqa: BLE001
            log.warning("backfill.get_entity_failed",
                        channel_id=channel_id, error=str(e))
            continue

        channel_count = 0
        async for msg in client.iter_messages(entity, limit=limit):
            if not (getattr(msg, "photo", None) or getattr(msg, "video", None)):
                continue
            channel_count += await _backfill_one_message(
                session_factory,
                msg=msg,
                channel_id=channel_id,
                client=client,
                minio_client=minio_client,
                bucket=bucket,
                settings=settings,
            )

        total += channel_count
        log.info("backfill.channel_done",
                 channel_id=channel_id, filled=channel_count)

    log.info("backfill.complete", total_filled=total)
    return total


async def _backfill_one_message(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    msg: Any,
    channel_id: int,
    client: TelegramClient,
    minio_client: Minio,
    bucket: str,
    settings: Any,
) -> int:
    """Match a Telegram message to a Post in our DB, find Media rows with
    storage_key=NULL, and run download_and_set_storage_keys for them.
    Returns the count of media rows we attempted to backfill (the helper
    may still leave some at NULL if Telethon's download fails)."""
    async with session_factory() as session:
        post_row = (await session.execute(
            select(Post.id).where(
                Post.channel_id == channel_id,
                Post.tg_message_id == int(msg.id),
            )
        )).one_or_none()
        if post_row is None:
            return 0
        post_id = post_row[0]

        media_rows = (await session.execute(
            select(Media.type, Media.tg_file_id).where(
                Media.post_id == post_id,
                Media.storage_key.is_(None),
            )
        )).all()
        if not media_rows:
            return 0

        media_values = [
            {"type": r.type, "tg_file_id": r.tg_file_id}
            for r in media_rows
        ]
        await download_and_set_storage_keys(
            session,
            msg=msg,
            channel_id=channel_id,
            new_post_id=post_id,
            media_values=media_values,
            client=client,
            minio_client=minio_client,
            bucket=bucket,
            settings=settings,
        )
        await session.commit()
        return len(media_rows)
