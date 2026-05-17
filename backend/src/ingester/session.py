import os


def default_sessions_dir() -> str:
    return os.environ.get("TG_SESSIONS_DIR", "/app/sessions")
