import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_alembic_upgrade_head(pg_container):
    backend_dir = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "POSTGRES_USER": pg_container["user"],
        "POSTGRES_PASSWORD": pg_container["password"],
        "POSTGRES_DB": pg_container["db"],
        "POSTGRES_HOST": pg_container["host"],
        "POSTGRES_PORT": str(pg_container["port"]),
        "REDIS_HOST": "x",
        "MINIO_ENDPOINT": "x:9000",
        "MINIO_ACCESS_KEY": "x",
        "MINIO_SECRET_KEY": "x",
        "API_JWT_SECRET": "x" * 32,
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"alembic upgrade failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"

    again = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert again.returncode == 0, again.stderr
    # After upgrade head, `alembic current` should report a revision tagged as (head).
    assert "(head)" in again.stdout, again.stdout

    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert heads.returncode == 0, heads.stderr
    head_revision = heads.stdout.strip().split()[0]
    assert head_revision in again.stdout, (
        f"alembic current ({again.stdout!r}) does not match head ({head_revision!r})"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_read_posts_table_exists(db_session) -> None:
    """0010 migration creates user_read_posts with the expected columns."""
    from sqlalchemy import text

    # Raises ProgrammingError (UndefinedTable/UndefinedColumn) if missing.
    await db_session.execute(
        text("SELECT user_id, post_id, read_at FROM user_read_posts WHERE false")
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_backfill_state_table_exists(db_session) -> None:
    """0011 migration creates channel_backfill_state with the expected columns."""
    from sqlalchemy import text

    await db_session.execute(
        text(
            "SELECT channel_id, fully_backfilled, oldest_seen_msg_id, "
            "last_backfill_at, locked_until "
            "FROM channel_backfill_state WHERE false"
        )
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_categories_table_exists(db_session) -> None:
    """0011 migration creates channel_categories with the expected columns."""
    from sqlalchemy import text

    await db_session.execute(
        text("SELECT channel_id, category FROM channel_categories WHERE false")
    )
