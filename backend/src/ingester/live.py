"""Live ingest: NewMessage event handler, channel subscription, and
restart catch-up.

Wires together normalize_message, upsert_post, and the photo/video
downloaders into the live pipeline.
"""
from __future__ import annotations

from functools import partial
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from telethon import TelegramClient, events
from minio import Minio

from ingester.normalize import normalize_message
from ingester.photos import download_and_store_photo, download_and_store_video_thumb
from shared.models import Channel, ChannelSubscription, Media, Post
from shared.repositories.posts import upsert_post

log = structlog.get_logger(__name__)


async def _load_active_chat_map(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[int, int]:
    """Return {tg_chat_id: channel_id} for all channel_subscriptions where status='active'."""
    async with session_factory() as session:
        res = await session.execute(
            select(Channel.tg_chat_id, Channel.id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(ChannelSubscription.status == "active")
        )
        return {chat_id: ch_id for chat_id, ch_id in res.all()}


async def on_new_message(
    event: Any,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    client: TelegramClient,
    channel_id_map: dict[int, int],
    bucket: str,
) -> None:
    """Handle a single NewMessage: normalize, upsert, download media if new."""
    chat_id = event.chat_id
    channel_id = channel_id_map.get(chat_id)
    if channel_id is None:
        # An event from a channel we don't track (cache miss after a recent join).
        # Best-effort: skip; the next subscribe will pick it up.
        try:
            log.debug("live.unknown_chat", chat_id=chat_id)
        except ValueError:
            pass
        return

    msg = event.message
    post_values, media_values = normalize_message(msg, channel_id)

    async with session_factory() as session:
        new_post_id = await upsert_post(session, post_values, media_values)
        if new_post_id is None:
            await session.commit()
            return  # duplicate

        # For each new media row, attempt the download and update storage_key.
        for media in media_values:
            mtype = media["type"]
            storage_key: str | None = None
            try:
                if mtype == "photo":
                    storage_key = await download_and_store_photo(
                        client, minio_client, msg,
                        channel_id=channel_id, bucket=bucket,
                    )
                elif mtype == "video":
                    storage_key = await download_and_store_video_thumb(
                        client, minio_client, msg,
                        channel_id=channel_id, bucket=bucket,
                    )
                # documents: no download for MVP.
            except Exception as e:  # noqa: BLE001
                try:
                    log.warning("live.download_failed",
                                channel_id=channel_id, msg_id=msg.id,
                                media_type=mtype, error=str(e))
                except ValueError:
                    pass  # stdout-cache issue under pytest

            if storage_key is not None:
                await session.execute(
                    update(Media)
                    .where(
                        Media.post_id == new_post_id,
                        Media.tg_file_id == media["tg_file_id"],
                    )
                    .values(storage_key=storage_key)
                )
        await session.commit()


async def subscribe_to_active_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
) -> dict[int, int]:
    """Load active channels from DB, register a NewMessage handler with
    `chats=[chat_ids...]`. Return the chat_id -> channel_id map for the caller."""
    chat_map = await _load_active_chat_map(session_factory)
    chat_ids = list(chat_map.keys())

    handler = partial(
        _dispatch,
        session_factory=session_factory,
        minio_client=minio_client,
        client=client,
        channel_id_map=chat_map,
        bucket=bucket,
    )
    client.add_event_handler(handler, events.NewMessage(chats=chat_ids))
    try:
        log.info("live.subscribed", count=len(chat_ids))
    except ValueError:
        pass
    return chat_map


async def _dispatch(event, *, session_factory, minio_client, client, channel_id_map, bucket):
    """Adapter that drops the implicit `event` positional arg into on_new_message kwargs."""
    await on_new_message(
        event,
        session_factory=session_factory,
        minio_client=minio_client,
        client=client,
        channel_id_map=channel_id_map,
        bucket=bucket,
    )


async def catchup_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    bucket: str,
    limit: int = 200,
) -> None:
    """For each active channel, fetch messages newer than the max ingested
    tg_message_id we have for that channel. Idempotent: missing posts are
    inserted; duplicates skip via upsert_post's ON CONFLICT.
    Called once at ingester boot, before subscribe_to_active_channels.
    """
    async with session_factory() as session:
        # Build a list of (channel_id, tg_chat_id, max_known_msg_id).
        from sqlalchemy import func as sa_func
        res = await session.execute(
            select(
                Channel.id, Channel.tg_chat_id,
                sa_func.coalesce(sa_func.max(Post.tg_message_id), 0),
            )
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .outerjoin(Post, Post.channel_id == Channel.id)
            .where(ChannelSubscription.status == "active")
            .group_by(Channel.id, Channel.tg_chat_id)
        )
        targets = res.all()

    for channel_id, tg_chat_id, max_known in targets:
        try:
            entity = await client.get_entity(tg_chat_id)
        except Exception as e:  # noqa: BLE001
            try:
                log.warning("live.catchup_get_entity_failed",
                            channel_id=channel_id, error=str(e))
            except ValueError:
                pass
            continue

        count = 0
        async for msg in client.iter_messages(entity, min_id=max_known, limit=limit):
            post_values, media_values = normalize_message(msg, channel_id)
            async with session_factory() as session:
                new_id = await upsert_post(session, post_values, media_values)
                if new_id is not None:
                    count += 1
                await session.commit()
        try:
            log.info("live.catchup_done", channel_id=channel_id, new=count)
        except ValueError:
            pass
