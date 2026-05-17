import os

# Ryuk reaper port mapping is flaky on Docker Desktop for Windows; disable it
# so testcontainers does not block on the reaper's auxiliary port discovery.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest
from testcontainers.postgres import PostgresContainer


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


@pytest.fixture
def configured_env(pg_container, monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", pg_container["user"])
    monkeypatch.setenv("POSTGRES_PASSWORD", pg_container["password"])
    monkeypatch.setenv("POSTGRES_DB", pg_container["db"])
    monkeypatch.setenv("POSTGRES_HOST", pg_container["host"])
    monkeypatch.setenv("POSTGRES_PORT", str(pg_container["port"]))
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "a")
    monkeypatch.setenv("MINIO_SECRET_KEY", "s")
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    from shared.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
