"""One-shot backfill of the last N days of posts for every active channel.

Recovers a gap left by a multi-day ingester outage. Boot `catchup_channels`
only pulls the newest ~200 messages above the last ingested id per channel,
so a busy channel that posted more than that during the downtime ends up
with a hole in the middle. This walks each active channel newest -> oldest
and ingests every message with `posted_at >= now - N days`, stopping at the
first message older than the cutoff.

Idempotent: `upsert_post` skips posts already present (ON CONFLICT) and media
is downloaded only for newly-inserted posts, so it is safe to run next to the
live ingester and safe to re-run.

This is a standalone sibling of `history_backfill` / `catchup_channels`. It
reuses only the leaf primitives (`normalize_*`, `upsert_post`,
`download_and_store_photo`) and keeps its own batch loop, so it stays
decoupled from the live and backfill workers. It is intentionally NOT wired
into `ingester.main` — it is a manual recovery tool, not a boot step.

Usage (inside the ingester container):
    docker compose exec ingester python -m scripts.backfill_last_days --days 8
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from minio import Minio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import PeerChannel

from ingester.normalize import normalize_album, normalize_message
from ingester.photos import download_and_store_photo
from shared.models import Channel, ChannelSubscription, Media
from shared.repositories.posts import upsert_post

log = structlog.get_logger(__name__)

DEFAULT_DAYS = 8


def cutoff_from(now: datetime, days: int) -> datetime:
    """Oldest `posted_at` to keep: `now - days`. `now` must be tz-aware UTC."""
    return now - timedelta(days=days)


def split_albums_solos(
    messages: list[Any],
) -> tuple[dict[int, list[Any]], list[Any]]:
    """Partition messages into albums (grouped by `grouped_id`) and solos."""
    albums: dict[int, list[Any]] = {}
    solos: list[Any] = []
    for m in messages:
        gid = getattr(m, "grouped_id", None)
        if gid is not None:
            albums.setdefault(int(gid), []).append(m)
        else:
            solos.append(m)
    return albums, solos


async def collect_window(
    client: TelegramClient, entity: Any, *, cutoff: datetime,
) -> list[Any]:
    """Walk a channel newest -> oldest and collect messages with
    `date >= cutoff`. Stops at the first message older than `cutoff`:
    `iter_messages` yields newest first, so everything past it is older too.
    """
    collected: list[Any] = []
    async for msg in client.iter_messages(entity):
        if msg.date < cutoff:
            break
        collected.append(msg)
    return collected


async def _download_photo(
    session: AsyncSession,
    *,
    msg: Any,
    channel_id: int,
    post_id: int,
    media: dict,
    client: TelegramClient,
    minio_client: Minio,
    bucket: str,
) -> None:
    """Download a single photo and write its storage_key onto the matching
    Media row. Videos and documents are skipped — the TMA renders an
    "open in Telegram" link for those, matching the live pipeline. Tolerant
    of per-file failures."""
    if media["type"] != "photo":
        return
    try:
        storage_key = await download_and_store_photo(
            client, minio_client, msg, channel_id=channel_id, bucket=bucket,
        )
    except Exception as e:  # noqa: BLE001 — one bad file must not kill the run
        log.warning(
            "backfill_last_days.download_failed",
            channel_id=channel_id, msg_id=getattr(msg, "id", None), error=str(e),
        )
        return
    if storage_key is not None:
        await session.execute(
            update(Media)
            .where(Media.post_id == post_id, Media.tg_file_id == media["tg_file_id"])
            .values(storage_key=storage_key)
        )


async def _ingest_batch(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    channel_id: int,
    messages: list[Any],
    bucket: str,
) -> int:
    """Album/solo split -> normalize -> upsert_post -> photo download for one
    channel's batch. Returns the number of newly-inserted posts. Modelled on
    history_backfill's ingest loop, kept local on purpose."""
    albums, solos = split_albums_solos(messages)
    new_count = 0

    for msgs in albums.values():
        post_values, media_values = normalize_album(msgs, channel_id)
        async with session_factory() as session:
            new_id = await upsert_post(session, post_values, media_values)
            if new_id is not None:
                ordered = sorted(msgs, key=lambda mm: int(mm.id))
                for media, msg in zip(media_values, ordered):
                    await _download_photo(
                        session, msg=msg, channel_id=channel_id, post_id=new_id,
                        media=media, client=client, minio_client=minio_client,
                        bucket=bucket,
                    )
                new_count += 1
            await session.commit()

    for msg in solos:
        post_values, media_values = normalize_message(msg, channel_id)
        async with session_factory() as session:
            new_id = await upsert_post(session, post_values, media_values)
            if new_id is not None:
                for media in media_values:
                    await _download_photo(
                        session, msg=msg, channel_id=channel_id, post_id=new_id,
                        media=media, client=client, minio_client=minio_client,
                        bucket=bucket,
                    )
                new_count += 1
            await session.commit()

    return new_count


async def backfill_last_days(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    *,
    bucket: str,
    days: int = DEFAULT_DAYS,
    channel_id: int | None = None,
) -> int:
    """Ingest all posts from the last `days` days for every active channel
    (or just `channel_id`, if given). Returns the total of newly-inserted
    posts across channels."""
    cutoff = cutoff_from(datetime.now(timezone.utc), days)

    async with session_factory() as session:
        q = (
            select(Channel.id, Channel.tg_chat_id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(ChannelSubscription.status == "active")
        )
        if channel_id is not None:
            q = q.where(Channel.id == channel_id)
        targets = (await session.execute(q)).all()

    log.info(
        "backfill_last_days.start",
        channels=len(targets), days=days, cutoff=cutoff.isoformat(),
    )

    total_new = 0
    for ch_id, tg_chat_id in targets:
        try:
            # PeerChannel for unambiguous resolution after a cold restart (7h6).
            entity = await client.get_entity(PeerChannel(tg_chat_id))
        except Exception as e:  # noqa: BLE001
            log.warning("backfill_last_days.get_entity_failed", channel_id=ch_id, error=str(e))
            continue

        try:
            messages = await collect_window(client, entity, cutoff=cutoff)
        except FloodWaitError as fw:
            log.warning("backfill_last_days.flood_wait", channel_id=ch_id, seconds=fw.seconds)
            continue
        except Exception as e:  # noqa: BLE001
            log.warning("backfill_last_days.fetch_failed", channel_id=ch_id, error=str(e))
            continue

        new_count = await _ingest_batch(
            client, session_factory, minio_client,
            channel_id=ch_id, messages=messages, bucket=bucket,
        )
        total_new += new_count
        log.info(
            "backfill_last_days.channel_done",
            channel_id=ch_id, fetched=len(messages), new=new_count,
        )

    log.info("backfill_last_days.complete", total_new=total_new)
    return total_new


async def _run_from_cli() -> None:  # pragma: no cover
    """Entrypoint for scripts/backfill_last_days.py."""
    from shared.config import get_settings
    from shared.db import make_engine, make_session_factory
    from shared.logging import configure_logging
    from shared.storage import ensure_bucket, make_storage_client
    from shared.tg.client_factory import make_client
    from ingester.session import default_sessions_dir

    parser = argparse.ArgumentParser(
        description="Backfill the last N days of posts for active channels.",
    )
    parser.add_argument(
        "--days", type=int, default=DEFAULT_DAYS,
        help=f"How many days back to ingest (default {DEFAULT_DAYS}).",
    )
    parser.add_argument(
        "--channel", type=int, default=None,
        help="Limit to a single Channel.id (default: all active channels).",
    )
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    if not settings.tg_api_id or not settings.tg_api_hash:
        raise SystemExit("TG_API_ID/TG_API_HASH not configured")

    client = make_client(settings, sessions_dir=default_sessions_dir())
    await client.start(phone=settings.tg_phone)
    engine = make_engine(settings.postgres_dsn)
    session_factory = make_session_factory(engine)
    minio_client = make_storage_client()
    ensure_bucket(minio_client, settings.minio_bucket)
    try:
        n = await backfill_last_days(
            client, session_factory, minio_client,
            bucket=settings.minio_bucket, days=args.days, channel_id=args.channel,
        )
        print(f"backfill_last_days: inserted {n} new posts (last {args.days}d)")  # noqa: T201
    finally:
        await client.disconnect()
        await engine.dispose()
