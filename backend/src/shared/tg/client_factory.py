import os

from telethon import TelegramClient

from shared.config import Settings


def make_client(settings: Settings, *, sessions_dir: str = "/app/sessions") -> TelegramClient:
    """Construct a TelegramClient for the userbot session.

    Ensures `sessions_dir` exists. The session file lives at
    `<sessions_dir>/<settings.tg_session_name>`; Telethon appends `.session`
    automatically.
    """
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, settings.tg_session_name)
    return TelegramClient(session_path, settings.tg_api_id, settings.tg_api_hash)
