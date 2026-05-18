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

    async def _noop(*a, **kw): return None

    with patch("ingester.main.make_client", return_value=fake_client), \
         patch("ingester.main.run_forever", side_effect=_noop), \
         patch("ingester.main.run_join_worker", side_effect=_noop), \
         patch("ingester.main.run_approval_poller", side_effect=_noop), \
         patch("ingester.main.run_refcount_sweep", side_effect=_noop), \
         patch("ingester.main.catchup_channels", side_effect=_noop), \
         patch("ingester.main.subscribe_to_active_channels", side_effect=_noop), \
         patch("ingester.main.make_storage_client") as fake_minio_factory, \
         patch("ingester.main.ensure_bucket") as fake_ensure, \
         patch("ingester.main.make_engine") as fake_engine_factory:
        fake_engine = MagicMock()
        fake_engine.dispose = AsyncMock()
        fake_engine_factory.return_value = fake_engine
        fake_minio_factory.return_value = MagicMock()
        from ingester.main import main
        asyncio.run(main())

    fake_client.start.assert_awaited_once()
    fake_client.disconnect.assert_awaited_once()
    fake_engine.dispose.assert_awaited_once()
    fake_ensure.assert_called_once()
