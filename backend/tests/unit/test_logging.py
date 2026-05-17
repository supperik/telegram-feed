import json

import structlog


def test_configure_logging_emits_json(capsys, monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    from shared.config import get_settings
    get_settings.cache_clear()

    from shared.logging import configure_logging
    configure_logging()

    log = structlog.get_logger("test")
    log.info("hello", who="world")

    out = capsys.readouterr().out.strip()
    assert out, "expected log on stdout"
    last_line = out.splitlines()[-1]
    payload = json.loads(last_line)
    assert payload["event"] == "hello"
    assert payload["who"] == "world"
    assert payload["level"] == "info"
