import os
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio


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
