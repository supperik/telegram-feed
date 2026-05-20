import asyncio
import signal

import structlog

from ingester.approval_poller import run_approval_poller
from ingester.backfill import backfill_recent_media
from ingester.backfill_channel_photos import backfill_channel_photos
from ingester.backfill_text_html import backfill_text_html
from ingester.history_backfill import run_history_backfill
from ingester.join_worker import run_join_worker
from ingester.live import catchup_channels, subscribe_to_active_channels
from ingester.merge_existing_albums import merge_existing_albums
from ingester.refcount_sweep import run_refcount_sweep
from ingester.session import default_sessions_dir
from shared.config import get_settings
from shared.db import make_engine, make_session_factory
from shared.logging import configure_logging
from shared.storage import ensure_bucket, make_storage_client
from shared.tg.client_factory import make_client

log = structlog.get_logger(__name__)


async def run_forever() -> None:
    """Block until SIGINT/SIGTERM. Plan 2 phases 1-4 will replace this with
    the actual concurrent task group; for Phase 0 the skeleton just waits."""
    stop = asyncio.Event()

    def _on_signal(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows asyncio loop doesn't support add_signal_handler.
            pass

    log.info("ingester.ready")
    await stop.wait()


async def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.tg_api_id or not settings.tg_api_hash:
        log.warning(
            "ingester.no_credentials",
            hint="set TG_API_ID and TG_API_HASH to start userbot",
        )
        return

    client = make_client(settings, sessions_dir=default_sessions_dir())
    await client.start(phone=settings.tg_phone)
    engine = make_engine(settings.postgres_dsn)
    session_factory = make_session_factory(engine)
    minio_client = make_storage_client()
    ensure_bucket(minio_client, settings.minio_bucket)
    try:
        me = await client.get_me()
        log.info(
            "ingester.connected",
            user_id=getattr(me, "id", None),
            username=getattr(me, "username", None),
        )
        # Catch up BEFORE subscribing live so we don't miss anything.
        await catchup_channels(client, session_factory, minio_client,
                                bucket=settings.minio_bucket, settings=settings)
        # Self-healing: re-fetch the last N messages for channels that
        # still have Media rows with storage_key=NULL (orphans from when
        # catchup didn't download media; see telegram-feed-pj0).
        # Idempotent: targets query is empty once everything is filled in.
        await backfill_recent_media(client, session_factory, minio_client,
                                     bucket=settings.minio_bucket, settings=settings,
                                     limit=50)
        # Refill text_html for posts ingested before this column was wired
        # to entities_to_html. Idempotent: no-op once everything is set.
        await backfill_text_html(client, session_factory)
        # Merge sibling Post-rows that belonged to the same Telegram media
        # group but were ingested as separate posts (pre-tg_grouped_id).
        # Idempotent: no-op once every Post has tg_grouped_id resolved.
        await merge_existing_albums(client, session_factory)
        # Fill Channel.photo_storage_key for active subscriptions whose
        # avatar was never cached (channels that existed before this
        # feature shipped). Idempotent across boots.
        await backfill_channel_photos(
            client, session_factory, minio_client,
            bucket=settings.minio_bucket,
        )
        # Live handler shares a mutable chat_map with the join worker so
        # newly-joined channels receive live updates without a restart
        # (telegram-feed-3bv).
        chat_map = await subscribe_to_active_channels(
            client, session_factory,
            minio_client=minio_client,
            bucket=settings.minio_bucket,
            settings=settings,
        )
        workers = [
            run_join_worker(
                client, session_factory,
                minio_client=minio_client, bucket=settings.minio_bucket,
                settings=settings,
                chat_map=chat_map,
            ),
            run_approval_poller(
                client, session_factory,
                minio_client=minio_client, bucket=settings.minio_bucket,
                settings=settings,
                poll_interval_s=settings.approval_poll_interval_s,
                timeout_days=settings.approval_timeout_days,
            ),
            run_refcount_sweep(session_factory, chat_map=chat_map),
            run_forever(),
        ]
        if settings.history_backfill_enabled:
            workers.append(
                run_history_backfill(
                    client, session_factory,
                    minio_client=minio_client, bucket=settings.minio_bucket,
                    settings=settings,
                )
            )
        await asyncio.gather(*workers)
    finally:
        await client.disconnect()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
