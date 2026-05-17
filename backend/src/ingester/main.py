import asyncio
import signal

import structlog

from ingester.join_worker import run_join_worker
from ingester.session import default_sessions_dir
from shared.config import get_settings
from shared.db import make_engine, make_session_factory
from shared.logging import configure_logging
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
    try:
        me = await client.get_me()
        log.info(
            "ingester.connected",
            user_id=getattr(me, "id", None),
            username=getattr(me, "username", None),
        )
        await asyncio.gather(
            run_forever(),
            run_join_worker(client, session_factory),
        )
    finally:
        await client.disconnect()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
