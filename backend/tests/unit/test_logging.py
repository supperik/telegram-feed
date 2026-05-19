import io
import json
import sys

import structlog


def _set_required_env(monkeypatch, *, fmt: str = "json") -> None:
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LOG_FORMAT", fmt)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    from shared.config import get_settings
    get_settings.cache_clear()


def test_logger_resolves_stdout_at_write_time(monkeypatch):
    """Regression for 5vt: PrintLoggerFactory(file=sys.stdout) captured the
    sys.stdout reference at configure time. When the surrounding context
    later replaced sys.stdout (pytest's capsys does this between tests),
    every subsequent log call wrote to the now-closed buffer and raised
    ValueError('I/O operation on closed file'). The fix must let structlog
    resolve sys.stdout at write time.
    """
    structlog.reset_defaults()
    _set_required_env(monkeypatch)

    stale = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stale)

    from shared.logging import configure_logging
    configure_logging()
    log = structlog.get_logger("repro_5vt")
    log.info("first")  # warms cache_logger_on_first_use binding
    stale.close()      # capsys-style teardown

    fresh = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fresh)

    log.info("second")  # MUST NOT raise

    assert "second" in fresh.getvalue()


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
