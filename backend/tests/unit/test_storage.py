from unittest.mock import MagicMock


def test_storage_client_factory_builds_minio_with_correct_args(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("MINIO_SECURE", "false")
    from shared.config import get_settings
    get_settings.cache_clear()

    fake_minio = MagicMock()
    monkeypatch.setattr("shared.storage.Minio", fake_minio)

    from shared.storage import make_storage_client
    make_storage_client()
    fake_minio.assert_called_once()
    kwargs = fake_minio.call_args.kwargs
    assert kwargs["endpoint"] == "m:9000"
    assert kwargs["access_key"] == "a"
    assert kwargs["secret_key"] == "s"
    assert kwargs["secure"] is False
