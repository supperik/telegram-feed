import os
from typing import AsyncIterator, Awaitable, Callable

# Ryuk reaper port mapping is flaky on Docker Desktop for Windows; disable it
# so testcontainers does not block on the reaper's auxiliary port discovery.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        sync_url = pg.get_connection_url()  # postgresql+psycopg2://...
        async_url = sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
        yield {
            "user": pg.username,
            "password": pg.password,
            "db": pg.dbname,
            "host": pg.get_container_host_ip(),
            "port": int(pg.get_exposed_port(5432)),
            "async_url": async_url,
        }


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as r:
        host = r.get_container_host_ip()
        port = int(r.get_exposed_port(6379))
        yield {"host": host, "port": port}


@pytest.fixture
def configured_env(pg_container, redis_container, monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", pg_container["user"])
    monkeypatch.setenv("POSTGRES_PASSWORD", pg_container["password"])
    monkeypatch.setenv("POSTGRES_DB", pg_container["db"])
    monkeypatch.setenv("POSTGRES_HOST", pg_container["host"])
    monkeypatch.setenv("POSTGRES_PORT", str(pg_container["port"]))
    monkeypatch.setenv("REDIS_HOST", redis_container["host"])
    monkeypatch.setenv("REDIS_PORT", str(redis_container["port"]))
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("TG_BOT_TOKEN", "1234:test-bot-token")
    from shared.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_session(pg_container) -> AsyncIterator[AsyncSession]:
    """Async session against the migrated Postgres container.

    The `apply_migrations` autouse fixture in `backend/tests/integration/conftest.py`
    guarantees the schema is at head before any integration test runs.
    """
    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def async_client(configured_env, pg_container, redis_container) -> AsyncIterator[AsyncClient]:
    """ASGI client bound to a freshly-built FastAPI app using the migrated test DB.

    httpx.ASGITransport does NOT trigger FastAPI lifespan events, so we replicate
    here exactly what the lifespan handler does: create engine, session factory,
    and Redis client and attach them to app.state.
    """
    from redis.asyncio import Redis

    from api.main import create_app

    app = create_app()
    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    app.state.engine = engine
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis(host=redis_container["host"], port=redis_container["port"], decode_responses=True)
    app.state.redis = redis
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        await redis.aclose()
        await engine.dispose()


SeedUser = Callable[..., Awaitable[int]]


@pytest_asyncio.fixture
async def seed_user(db_session) -> SeedUser:
    from shared.models import User

    async def _seed(*, tg_user_id: int, first_name: str = "Ada", username: str | None = "ada") -> int:
        u = User(tg_user_id=tg_user_id, tg_first_name=first_name, tg_username=username)
        db_session.add(u)
        await db_session.commit()
        await db_session.refresh(u)
        return u.id

    return _seed
