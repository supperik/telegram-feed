from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


def test_engine_factory_returns_async_engine(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    monkeypatch.setenv("POSTGRES_HOST", "h")
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("MINIO_ENDPOINT", "m:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    from shared.config import get_settings
    get_settings.cache_clear()

    from shared.db import make_engine, make_session_factory

    engine = make_engine("postgresql+asyncpg://u:p@h:5432/d")
    assert isinstance(engine, AsyncEngine)
    factory = make_session_factory(engine)
    sess = factory()
    assert isinstance(sess, AsyncSession)
