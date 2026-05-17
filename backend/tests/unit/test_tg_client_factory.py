from unittest.mock import patch


def test_make_client_uses_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("TG_API_ID", "12345")
    monkeypatch.setenv("TG_API_HASH", "deadbeef")
    monkeypatch.setenv("TG_SESSION_NAME", "ut_session")
    from shared.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()

    with patch("shared.tg.client_factory.TelegramClient") as TC:
        from shared.tg.client_factory import make_client
        make_client(settings, sessions_dir=str(tmp_path))
        TC.assert_called_once()
        args, _ = TC.call_args
        assert str(tmp_path) in args[0]
        assert args[0].endswith("ut_session")
        assert args[1] == 12345
        assert args[2] == "deadbeef"


def test_make_client_creates_sessions_dir_if_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("TG_API_ID", "1")
    monkeypatch.setenv("TG_API_HASH", "abc")
    from shared.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()

    target = tmp_path / "nested" / "dir"
    with patch("shared.tg.client_factory.TelegramClient"):
        from shared.tg.client_factory import make_client
        make_client(settings, sessions_dir=str(target))
    assert target.is_dir()
