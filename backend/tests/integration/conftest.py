import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from testcontainers.minio import MinioContainer


@pytest.fixture(scope="session")
def minio_container() -> Iterator[dict]:
    """Session-scoped MinIO testcontainer. Yields {endpoint, access_key, secret_key}.

    The default image pin in testcontainers (2022-12) is fine for e2e tests —
    we only exercise bucket creation + put_object + get_object, all stable APIs.
    """
    with MinioContainer() as mc:
        yield mc.get_config()


@pytest_asyncio.fixture(autouse=True)
async def _flush_redis_between_tests(redis_container):
    # Rate-limit / cache state leaks between integration tests otherwise:
    # one test's auth calls would push the sliding-window over the cap for
    # the next test using the same client IP ("testclient").
    from redis.asyncio import Redis

    r = Redis(host=redis_container["host"], port=redis_container["port"], decode_responses=True)
    try:
        await r.flushdb()
    finally:
        await r.aclose()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _truncate_postgres_between_tests(apply_migrations, pg_container):
    # pg_container is session-scoped, so committed rows leak between tests —
    # most visibly as uq_channels_username violations when two tests insert a
    # Channel with the same hardcoded username. Truncate every data table
    # (resetting identity sequences) before each test.
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
            tables = ", ".join(row[0] for row in result)
            await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
    finally:
        await engine.dispose()
    yield


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(pg_container, redis_container):
    backend_dir = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "POSTGRES_USER": pg_container["user"],
        "POSTGRES_PASSWORD": pg_container["password"],
        "POSTGRES_DB": pg_container["db"],
        "POSTGRES_HOST": pg_container["host"],
        "POSTGRES_PORT": str(pg_container["port"]),
        "REDIS_HOST": redis_container["host"],
        "REDIS_PORT": str(redis_container["port"]),
        "MINIO_ENDPOINT": "x:9000",
        "MINIO_ACCESS_KEY": "x",
        "MINIO_SECRET_KEY": "x",
        "API_JWT_SECRET": "x" * 32,
        "TG_BOT_TOKEN": "1234:test-bot-token",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    yield
