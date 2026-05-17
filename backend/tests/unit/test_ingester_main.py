import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _set_env(monkeypatch, **extra):
    base = {
        "POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p", "POSTGRES_DB": "d",
        "POSTGRES_HOST": "h", "REDIS_HOST": "r",
        "MINIO_ENDPOINT": "m:9000", "MINIO_ACCESS_KEY": "a", "MINIO_SECRET_KEY": "s",
        "API_JWT_SECRET": "x" * 32,
    }
    base.update(extra)
    for k, v in base.items():
        monkeypatch.setenv(k, v)


def test_main_warns_and_exits_when_no_credentials(monkeypatch):
    _set_env(monkeypatch)
    from shared.config import get_settings
    get_settings.cache_clear()

    from ingester.main import main
    # Should return cleanly without trying to connect (no patches needed).
    asyncio.run(main())


def test_main_connects_via_factory_and_disconnects(monkeypatch):
    _set_env(monkeypatch, TG_API_ID="12345", TG_API_HASH="deadbeef", TG_PHONE="+10000000000")
    from shared.config import get_settings
    get_settings.cache_clear()

    fake_client = MagicMock()
    fake_client.start = AsyncMock()
    fake_client.disconnect = AsyncMock()
    fake_client.get_me = AsyncMock(return_value=MagicMock(id=1, username="bot"))

    async def fake_run_forever():
        return None

    with patch("ingester.main.make_client", return_value=fake_client), \
         patch("ingester.main.run_forever", side_effect=fake_run_forever):
        from ingester.main import main
        asyncio.run(main())

    fake_client.start.assert_awaited_once()
    fake_client.disconnect.assert_awaited_once()
    fake_client.get_me.assert_awaited_once()
