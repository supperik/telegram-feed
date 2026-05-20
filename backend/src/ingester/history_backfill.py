"""History backfill worker: pulls older channel posts into the shared pool.

Eligibility = a following user has <= K unread posts in the channel
(read-watermark with prefetch buffer). See
docs/superpowers/specs/2026-05-20-history-backfill-design.md.

The ingest pipeline is identical to catchup_channels — the only difference
is iter_messages(max_id=...) (older) instead of min_id (newer).
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerChannel

# _download_one_and_update_storage_key is module-private to live.py, but it is
# the exact per-album-member photo download catchup_channels uses — reused here
# on purpose rather than duplicated.
from ingester.live import (
    _download_one_and_update_storage_key,
    download_and_set_storage_keys,
)
from ingester.normalize import normalize_album, normalize_message
from shared.repositories.channel_backfill import (
    defer_after_flood_wait,
    mark_fully_backfilled,
    release_lock,
    select_eligible_channels,
    try_acquire_lock,
)
from shared.repositories.posts import upsert_post

log = structlog.get_logger(__name__)


async def run_history_backfill(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
    settings: Any,
) -> None:
    """Background loop. Mirrors run_approval_poller / run_refcount_sweep."""
    log.info(
        "history_backfill.started",
        interval_s=settings.history_backfill_interval_s,
    )
    while True:
        try:
            await _one_tick(
                client, session_factory, minio_client,
                bucket=bucket, settings=settings,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("history_backfill.tick_failed", error=str(e))
        await asyncio.sleep(settings.history_backfill_interval_s)


async def _one_tick(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    bucket: str,
    settings: Any,
) -> None:
    async with session_factory() as session:
        eligible = await select_eligible_channels(
            session,
            unread_threshold=settings.history_backfill_unread_threshold,
            limit=settings.history_backfill_channels_per_tick,
        )

    for channel_id, tg_chat_id, oldest_cursor in eligible:
        async with session_factory() as session:
            got_lock = await try_acquire_lock(
                session,
                channel_id=channel_id,
                ttl_seconds=settings.history_backfill_lock_ttl_s,
            )
            await session.commit()
        if not got_lock:
            continue
        await _backfill_one_channel(
            client, session_factory, minio_client,
            channel_id=channel_id, tg_chat_id=tg_chat_id,
            oldest_cursor=oldest_cursor, bucket=bucket, settings=settings,
        )


async def _backfill_one_channel(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    channel_id: int,
    tg_chat_id: int,
    oldest_cursor: int,
    bucket: str,
    settings: Any,
) -> None:
    """Fetch one batch of messages older than oldest_cursor and ingest them.
    Assumes the lock is already held (caller acquired it)."""
    try:
        # PeerChannel for unambiguous resolution after a cold restart (7h6).
        entity = await client.get_entity(PeerChannel(tg_chat_id))
        collected: list[Any] = []
        async for msg in client.iter_messages(
            entity,
            max_id=oldest_cursor,
            limit=settings.history_backfill_batch_size,
        ):
            collected.append(msg)
    except FloodWaitError as fw:
        log.warning(
            "history_backfill.flood_wait",
            channel_id=channel_id, seconds=fw.seconds,
        )
        async with session_factory() as session:
            await defer_after_flood_wait(
                session, channel_id=channel_id, seconds=fw.seconds,
            )
            await session.commit()
        return
    except Exception as e:  # noqa: BLE001
        log.warning(
            "history_backfill.fetch_failed", channel_id=channel_id, error=str(e),
        )
        async with session_factory() as session:
            await release_lock(
                session, channel_id=channel_id, oldest_seen_msg_id=oldest_cursor,
            )
            await session.commit()
        return

    if not collected:
        async with session_factory() as session:
            await mark_fully_backfilled(session, channel_id=channel_id)
            await session.commit()
        log.info("history_backfill.fully_backfilled", channel_id=channel_id)
        return

    # Cursor = oldest message *seen*, not oldest post stored — a batch of
    # non-post service messages must still advance it (no stall).
    new_oldest = min(int(m.id) for m in collected)
    await _ingest_messages(
        client, session_factory, minio_client,
        channel_id=channel_id, messages=collected,
        bucket=bucket, settings=settings,
    )
    async with session_factory() as session:
        await release_lock(
            session, channel_id=channel_id, oldest_seen_msg_id=new_oldest,
        )
        await session.commit()
    log.info(
        "history_backfill.channel_done",
        channel_id=channel_id, fetched=len(collected), new_oldest=new_oldest,
    )


async def _ingest_messages(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    channel_id: int,
    messages: list[Any],
    bucket: str,
    settings: Any,
) -> None:
    """Album/solo split -> normalize -> upsert_post -> media download.
    A near-copy of catchup_channels' per-message handling (ingester/live.py)."""
    albums: dict[int, list[Any]] = {}
    solos: list[Any] = []
    for m in messages:
        gid = getattr(m, "grouped_id", None)
        if gid is not None:
            albums.setdefault(int(gid), []).append(m)
        else:
            solos.append(m)

    for _gid, msgs in albums.items():
        post_values, media_values = normalize_album(msgs, channel_id)
        async with session_factory() as session:
            new_id = await upsert_post(session, post_values, media_values)
            if new_id is not None:
                ordered = sorted(msgs, key=lambda mm: int(mm.id))
                for media, msg in zip(media_values, ordered):
                    await _download_one_and_update_storage_key(
                        session, msg=msg, channel_id=channel_id,
                        post_id=new_id, media=media, client=client,
                        minio_client=minio_client, bucket=bucket,
                        settings=settings,
                    )
            await session.commit()

    for msg in solos:
        post_values, media_values = normalize_message(msg, channel_id)
        async with session_factory() as session:
            new_id = await upsert_post(session, post_values, media_values)
            if new_id is not None:
                await download_and_set_storage_keys(
                    session, msg=msg, channel_id=channel_id,
                    new_post_id=new_id, media_values=media_values,
                    client=client, minio_client=minio_client,
                    bucket=bucket, settings=settings,
                )
            await session.commit()
