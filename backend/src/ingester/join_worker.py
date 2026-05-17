import asyncio
from datetime import datetime, timezone

import structlog
from minio import Minio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.channels import JoinChannelRequest

from ingester.normalize import normalize_message
from shared.models import ChannelSubscription
from shared.repositories.channels import increment_ref_count, upsert_channel
from shared.repositories.join_queue import (
    mark_join_done,
    mark_join_failed,
    pop_pending_join_request,
)
from shared.repositories.posts import upsert_post

log = structlog.get_logger(__name__)


async def _backfill_channel(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    entity,
    channel_id: int,
    *,
    limit: int,
    bucket: str,
) -> None:
    """Fetch the most recent `limit` messages from `entity` and upsert each.

    NOTE: P4 keeps backfill simple — no photo download in backfill yet,
    only live and catchup download. This is a tradeoff: backfill stays fast
    at the cost of older posts initially having no thumbnails. Live ingest
    downloads everything going forward.
    """
    async for msg in client.iter_messages(entity, limit=limit):
        post_values, media_values = normalize_message(msg, channel_id)
        async with session_factory() as session:
            await upsert_post(session, post_values, media_values)
            await session.commit()

    # After backfill, mark subscription active.
    async with session_factory() as session:
        await session.execute(
            update(ChannelSubscription)
            .where(ChannelSubscription.channel_id == channel_id)
            .values(status="active", backfilled_at=datetime.now(tz=timezone.utc))
        )
        await session.commit()


async def _handle_one_pending(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
) -> None:
    """Pop one pending join, attempt it, commit the outcome. No-op if empty."""
    async with session_factory() as session:
        pending = await pop_pending_join_request(session)
        if pending is None:
            await session.commit()
            return

        username = pending.channel_username
        queue_id = pending.id
        try:
            entity = await client.get_entity(username)
        except UsernameNotOccupiedError:
            await mark_join_failed(
                session, queue_id=queue_id, error_reason="username_not_occupied"
            )
            await session.commit()
            log.warning("join_worker.username_not_occupied", username=username, queue_id=queue_id)
            return
        except UsernameInvalidError:
            await mark_join_failed(
                session, queue_id=queue_id, error_reason="username_invalid"
            )
            await session.commit()
            log.warning("join_worker.username_invalid", username=username, queue_id=queue_id)
            return
        except ChannelPrivateError:
            await mark_join_failed(
                session, queue_id=queue_id, error_reason="channel_private"
            )
            await session.commit()
            log.warning("join_worker.channel_private", username=username, queue_id=queue_id)
            return
        except FloodWaitError as e:
            await session.rollback()  # let the row revert to pending? actually no — it's already in_progress.
            # Sleep and let the next loop iteration retry (the in_progress row stays as-is).
            log.info("join_worker.flood_wait", seconds=e.seconds, queue_id=queue_id)
            await asyncio.sleep(e.seconds + 1)
            return

        try:
            await client(JoinChannelRequest(entity))
        except FloodWaitError as e:
            await session.rollback()
            log.info("join_worker.flood_wait_on_join", seconds=e.seconds, queue_id=queue_id)
            await asyncio.sleep(e.seconds + 1)
            return
        except Exception as e:  # noqa: BLE001 — keep loop alive
            await mark_join_failed(
                session,
                queue_id=queue_id,
                error_reason=f"join_failed:{type(e).__name__}",
            )
            await session.commit()
            log.error("join_worker.join_failed", username=username, error=str(e))
            return

        channel = await upsert_channel(
            session,
            tg_chat_id=int(entity.id),
            username=getattr(entity, "username", None) or username,
            title=getattr(entity, "title", None) or username,
        )
        await increment_ref_count(session, channel_id=channel.id)
        await mark_join_done(session, queue_id=queue_id, channel_id=channel.id)
        await session.commit()
        log.info(
            "join_worker.joined",
            channel_id=channel.id,
            tg_chat_id=channel.tg_chat_id,
            username=username,
        )

    # Backfill happens outside the join session — it owns its own sessions.
    await _backfill_channel(
        client, session_factory, minio_client, entity, channel.id,
        limit=50, bucket=bucket,
    )


async def run_join_worker(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
    poll_interval_s: float = 2.0,
) -> None:
    log.info("join_worker.started", poll_interval_s=poll_interval_s)
    while True:
        try:
            await _handle_one_pending(
                client, session_factory,
                minio_client=minio_client, bucket=bucket,
            )
        except Exception as e:  # noqa: BLE001 — keep loop alive
            log.exception("join_worker.loop_error", error=str(e))
        await asyncio.sleep(poll_interval_s)
