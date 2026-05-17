import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def test_ingester_main_connects_and_logs_ready(monkeypatch):
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
    monkeypatch.setenv("TG_PHONE", "+10000000000")
    from shared.config import get_settings
    get_settings.cache_clear()

    fake_client = MagicMock()
    fake_client.start = AsyncMock()
    fake_client.disconnect = AsyncMock()
    fake_client.get_me = AsyncMock(return_value=MagicMock(id=1, username="bot"))

    async def fake_run_forever(client):
        return None

    with patch("ingester.main.TelegramClient", return_value=fake_client), \
         patch("ingester.main.run_forever", side_effect=fake_run_forever):
        from ingester.main import main
        asyncio.run(main())

    fake_client.start.assert_awaited_once()
    fake_client.disconnect.assert_awaited_once()
