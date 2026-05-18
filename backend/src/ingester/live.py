"""Live ingest: NewMessage event handler, channel subscription, and
restart catch-up.

Wires together normalize_message, upsert_post, and the photo/video
downloaders into the live pipeline.
"""
from __future__ import annotations

from functools import partial
from typing import Any

import structlog
from minio import Minio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from telethon.utils import get_peer_id

from ingester.normalize import normalize_message
from ingester.photos import download_and_store_photo, download_and_store_video_thumb
from shared.models import Channel, ChannelSubscription, Media, Post
from shared.repositories.posts import upsert_post

log = structlog.get_logger(__name__)


def _to_marked_chat_id(positive_supergroup_id: int) -> int:
    """Convert a raw positive Telegram supergroup id (as stored in
    Channel.tg_chat_id) to the marked peer-id form Telethon uses on
    NewMessage events (e.g. 1319248631 → -1001319248631).

    Telethon's event.chat_id is always the marked form; passing the raw
    positive id into NewMessage(chats=...) or using it as a dict key for
    event.chat_id lookups silently never matches. This is the conversion
    that closes that mismatch.
    """
    return get_peer_id(PeerChannel(channel_id=positive_supergroup_id))


async def _load_active_chat_map(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[int, int]:
    """Return {marked_chat_id: channel_id} for active channel_subscriptions.

    Keys are MARKED peer IDs (-100xxxxx), matching Telethon's
    event.chat_id format. Channel.tg_chat_id in the DB is the raw
    positive supergroup id; we normalize on the way out.
    """
    async with session_factory() as session:
        res = await session.execute(
            select(Channel.tg_chat_id, Channel.id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(ChannelSubscription.status == "active")
        )
        return {_to_marked_chat_id(chat_id): ch_id for chat_id, ch_id in res.all()}


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

        await download_and_set_storage_keys(
            session,
            msg=msg,
            channel_id=channel_id,
            new_post_id=new_post_id,
            media_values=media_values,
            client=client,
            minio_client=minio_client,
            bucket=bucket,
        )
        await session.commit()


async def download_and_set_storage_keys(
    session: AsyncSession,
    *,
    msg: Any,
    channel_id: int,
    new_post_id: int,
    media_values: list[dict],
    client: TelegramClient,
    minio_client: Minio,
    bucket: str,
) -> None:
    """Download photo / video-thumb for each new media row and UPDATE
    storage_key. Tolerant of per-media failures."""
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


async def subscribe_to_active_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
) -> dict[int, int]:
    """Load active channels from DB and register an UNFILTERED NewMessage
    handler. Returns the {marked_chat_id: channel_id} map.

    The handler intentionally has NO chats=... filter. Telethon resolves
    chats=[...] to a static set at subscribe time, so (a) channels joined
    later aren't seen until restart (telegram-feed-3bv) and (b) if the
    wrong id format is passed (positive vs marked), every event is silently
    dropped. Instead we accept all NewMessage events and filter inside
    on_new_message via the returned (mutable) chat_map dict — join_worker
    extends this dict after a successful join so the new channel
    immediately receives live updates.
    """
    chat_map = await _load_active_chat_map(session_factory)

    handler = partial(
        _dispatch,
        session_factory=session_factory,
        minio_client=minio_client,
        client=client,
        channel_id_map=chat_map,
        bucket=bucket,
    )
    client.add_event_handler(handler, events.NewMessage())
    try:
        log.info("live.subscribed", count=len(chat_map))
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
                    await download_and_set_storage_keys(
                        session,
                        msg=msg,
                        channel_id=channel_id,
                        new_post_id=new_id,
                        media_values=media_values,
                        client=client,
                        minio_client=minio_client,
                        bucket=bucket,
                    )
                await session.commit()
        try:
            log.info("live.catchup_done", channel_id=channel_id, new=count)
        except ValueError:
            pass
