import asyncio
import signal

import structlog

from ingester.backfill import backfill_recent_media
from ingester.join_worker import run_join_worker
from ingester.live import catchup_channels, subscribe_to_active_channels
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
                                bucket=settings.minio_bucket)
        # Self-healing: re-fetch the last N messages for channels that
        # still have Media rows with storage_key=NULL (orphans from when
        # catchup didn't download media; see telegram-feed-pj0).
        # Idempotent: targets query is empty once everything is filled in.
        await backfill_recent_media(client, session_factory, minio_client,
                                     bucket=settings.minio_bucket, limit=50)
        await subscribe_to_active_channels(client, session_factory,
                                            minio_client=minio_client,
                                            bucket=settings.minio_bucket)
        await asyncio.gather(
            run_join_worker(client, session_factory,
                            minio_client=minio_client, bucket=settings.minio_bucket),
            run_refcount_sweep(client, session_factory),
            run_forever(),
        )
    finally:
        await client.disconnect()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
