import asyncio
import os
import signal

import structlog
from telethon import TelegramClient

from shared.config import get_settings
from shared.logging import configure_logging

log = structlog.get_logger(__name__)


async def run_forever(client: TelegramClient) -> None:
    """Block until SIGINT/SIGTERM. Plan 2 will replace this with the
    NewMessage event loop; the skeleton just waits."""
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

    sessions_dir = os.environ.get("TG_SESSIONS_DIR", "/app/sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, settings.tg_session_name)

    client = TelegramClient(session_path, settings.tg_api_id, settings.tg_api_hash)
    await client.start(phone=settings.tg_phone)
    try:
        me = await client.get_me()
        log.info(
            "ingester.connected",
            user_id=getattr(me, "id", None),
            username=getattr(me, "username", None),
        )
        await run_forever(client)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
