import pytest
from pydantic import ValidationError


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("MINIO_BUCKET", "media")
    monkeypatch.setenv("MINIO_SECURE", "false")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_API_ID", "1")
    monkeypatch.setenv("TG_API_HASH", "abc")
    monkeypatch.setenv("TG_PHONE", "+10000000000")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("ENV", "test")

    from shared.config import Settings, get_settings
    get_settings.cache_clear()
    s = Settings()
    assert s.postgres_user == "u"
    assert s.postgres_port == 5432
    assert s.minio_secure is False
    assert s.api_jwt_secret == "x" * 32
    assert s.env == "test"
    assert s.postgres_dsn.startswith("postgresql+asyncpg://")


def test_settings_rejects_missing_required(monkeypatch):
    for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
              "POSTGRES_HOST", "REDIS_HOST", "MINIO_ENDPOINT",
              "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "API_JWT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    from shared.config import Settings
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def _base_env(monkeypatch):
    for k, v in {
        "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p", "POSTGRES_DB": "d",
        "POSTGRES_HOST": "h", "REDIS_HOST": "r", "MINIO_ENDPOINT": "m:9000",
        "MINIO_ACCESS_KEY": "a", "MINIO_SECRET_KEY": "s", "API_JWT_SECRET": "x" * 32,
    }.items():
        monkeypatch.setenv(k, v)


def test_history_backfill_settings_defaults(monkeypatch):
    _base_env(monkeypatch)
    from shared.config import Settings, get_settings
    get_settings.cache_clear()
    s = Settings()
    assert s.history_backfill_enabled is True
    assert s.history_backfill_interval_s == 300
    assert s.history_backfill_unread_threshold == 20
    assert s.history_backfill_batch_size == 100
    assert s.history_backfill_lock_ttl_s == 300
    assert s.history_backfill_channels_per_tick == 20


def test_history_backfill_settings_env_override(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("HISTORY_BACKFILL_ENABLED", "false")
    monkeypatch.setenv("HISTORY_BACKFILL_UNREAD_THRESHOLD", "5")
    from shared.config import Settings, get_settings
    get_settings.cache_clear()
    s = Settings()
    assert s.history_backfill_enabled is False
    assert s.history_backfill_unread_threshold == 5
