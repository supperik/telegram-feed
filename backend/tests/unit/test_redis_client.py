from unittest.mock import patch


def test_redis_client_constructs_with_dsn(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    from shared.config import get_settings
    get_settings.cache_clear()

    with patch("shared.redis_client.redis.from_url") as from_url:
        from shared.redis_client import make_redis_client
        make_redis_client()
        from_url.assert_called_once_with("redis://r:6379/0", decode_responses=True)
