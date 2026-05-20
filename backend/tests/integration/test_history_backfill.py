"""Integration tests for the history_backfill worker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from telethon.errors import FloodWaitError

from ingester.history_backfill import _backfill_one_channel, _one_tick
from shared.models import (
    Channel,
    ChannelBackfillState,
    ChannelSubscription,
    Post,
    User,
    UserReadPost,
    UserSource,
)
from shared.repositories.channel_backfill import try_acquire_lock
from tests.integration._fakes.fake_telethon import (
    FakeTelethonClient,
    make_fake_message,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_POSTED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _settings(monkeypatch, pg_container, redis_container, **overrides):
    """Build Settings with the backfill knobs dialled low for tests."""
    from shared.config import get_settings

    env = {
        "POSTGRES_USER": pg_container["user"],
        "POSTGRES_PASSWORD": pg_container["password"],
        "POSTGRES_DB": pg_container["db"],
        "POSTGRES_HOST": pg_container["host"],
        "POSTGRES_PORT": str(pg_container["port"]),
        "REDIS_HOST": redis_container["host"],
        "REDIS_PORT": str(redis_container["port"]),
        "MINIO_ENDPOINT": "x:9000", "MINIO_ACCESS_KEY": "x", "MINIO_SECRET_KEY": "x",
        "API_JWT_SECRET": "x" * 32, "TG_BOT_TOKEN": "1234:test-bot-token",
        "HISTORY_BACKFILL_UNREAD_THRESHOLD": "2",
        "HISTORY_BACKFILL_BATCH_SIZE": "100",
        "HISTORY_BACKFILL_CHANNELS_PER_TICK": "20",
        "HISTORY_BACKFILL_LOCK_TTL_S": "300",
    }
    env.update(overrides)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    return get_settings()


async def _seed(db_session, *, tg_chat_id, msg_ids, read_all=True, tg_user_id):
    """Channel + active sub + one follower; posts; follower reads them all
    (read_all) so the channel's unread count is 0 -> eligible at K=2."""
    ch = Channel(tg_chat_id=tg_chat_id, title="t", username=f"c{tg_chat_id}")
    db_session.add(ch)
    await db_session.flush()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    u = User(tg_user_id=tg_user_id, tg_first_name="U", tg_username=f"u{tg_user_id}")
    db_session.add(u)
    await db_session.flush()
    db_session.add(UserSource(user_id=u.id, channel_id=ch.id))
    post_ids = []
    for mid in msg_ids:
        p = Post(channel_id=ch.id, tg_message_id=mid, posted_at=_POSTED_AT)
        db_session.add(p)
        await db_session.flush()
        post_ids.append(p.id)
    if read_all:
        for pid in post_ids:
            db_session.add(UserReadPost(user_id=u.id, post_id=pid))
    await db_session.commit()
    return ch.id


async def test_one_tick_backfills_older_posts_then_self_limits(
    pg_container, redis_container, db_session, monkeypatch
):
    """Eligible channel -> one tick pulls older solo + album messages; a
    second tick is a no-op because the new posts refilled the buffer."""
    settings = _settings(monkeypatch, pg_container, redis_container)
    chat_id = 8101001
    channel_id = await _seed(
        db_session, tg_chat_id=chat_id, msg_ids=[100, 101, 102], tg_user_id=8102001
    )

    # Older messages, newest-first: three solos + a 3-message album.
    fake = FakeTelethonClient()
    fake.catchup_messages[chat_id] = [
        make_fake_message(id=99, text="m99"),
        make_fake_message(id=98, text="m98"),
        make_fake_message(id=97, text="m97"),
        make_fake_message(id=96, text="a96", grouped_id=500),
        make_fake_message(id=95, text="a95", grouped_id=500),
        make_fake_message(id=94, text="a94", grouped_id=500),
    ]

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _one_tick(fake, session_factory, MagicMock(),
                        bucket="media", settings=settings)

        async with session_factory() as s:
            posts = (await s.execute(
                select(Post).where(Post.channel_id == channel_id))).scalars().all()
            ids = sorted(p.tg_message_id for p in posts)
            # 100/101/102 original + 97/98/99 solos + album folded to id 94.
            assert ids == [94, 97, 98, 99, 100, 101, 102]
            album = [p for p in posts if p.tg_grouped_id == 500]
            assert len(album) == 1

            st = await s.get(ChannelBackfillState, channel_id)
            assert st.oldest_seen_msg_id == 94
            assert st.locked_until is None
            assert st.fully_backfilled is False

        # Second tick: 4 new unread posts > K(2) -> channel no longer eligible.
        await _one_tick(fake, session_factory, MagicMock(),
                        bucket="media", settings=settings)
        async with session_factory() as s:
            count = len((await s.execute(
                select(Post).where(Post.channel_id == channel_id))).scalars().all())
            assert count == 7
    finally:
        await engine.dispose()


async def test_one_tick_marks_fully_backfilled_when_no_older_messages(
    pg_container, redis_container, db_session, monkeypatch
):
    settings = _settings(monkeypatch, pg_container, redis_container)
    chat_id = 8101002
    channel_id = await _seed(
        db_session, tg_chat_id=chat_id, msg_ids=[100, 101], tg_user_id=8102002
    )
    fake = FakeTelethonClient()
    fake.catchup_messages[chat_id] = []  # nothing older

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _one_tick(fake, session_factory, MagicMock(),
                        bucket="media", settings=settings)
        async with session_factory() as s:
            st = await s.get(ChannelBackfillState, channel_id)
            assert st.fully_backfilled is True
            assert st.locked_until is None
    finally:
        await engine.dispose()


async def test_backfill_one_channel_flood_wait_defers(
    pg_container, redis_container, db_session, monkeypatch
):
    settings = _settings(monkeypatch, pg_container, redis_container)
    channel_id = await _seed(
        db_session, tg_chat_id=8101003, msg_ids=[100], tg_user_id=8102003
    )
    flood = FloodWaitError(request=None)
    flood.seconds = 444

    client = MagicMock()
    client.get_entity = AsyncMock(return_value=MagicMock(id=8101003))
    client.iter_messages = MagicMock(side_effect=flood)

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            await try_acquire_lock(s, channel_id=channel_id, ttl_seconds=300)
            await s.commit()
        await _backfill_one_channel(
            client, session_factory, MagicMock(),
            channel_id=channel_id, tg_chat_id=8101003, oldest_cursor=100,
            bucket="media", settings=settings,
        )
        async with session_factory() as s:
            st = await s.get(ChannelBackfillState, channel_id)
            assert st.locked_until > datetime.now(timezone.utc) + timedelta(seconds=300)
            assert st.fully_backfilled is False
    finally:
        await engine.dispose()


async def test_backfill_one_channel_get_entity_failure_releases_lock(
    pg_container, redis_container, db_session, monkeypatch
):
    settings = _settings(monkeypatch, pg_container, redis_container)
    channel_id = await _seed(
        db_session, tg_chat_id=8101004, msg_ids=[100], tg_user_id=8102004
    )
    client = MagicMock()
    client.get_entity = AsyncMock(side_effect=ValueError("no entity"))

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as s:
            await try_acquire_lock(s, channel_id=channel_id, ttl_seconds=300)
            await s.commit()
        await _backfill_one_channel(
            client, session_factory, MagicMock(),
            channel_id=channel_id, tg_chat_id=8101004, oldest_cursor=100,
            bucket="media", settings=settings,
        )
        async with session_factory() as s:
            st = await s.get(ChannelBackfillState, channel_id)
            assert st.locked_until is None
            assert st.fully_backfilled is False
            assert st.oldest_seen_msg_id == 100
    finally:
        await engine.dispose()
