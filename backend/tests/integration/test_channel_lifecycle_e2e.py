"""End-to-end channel lifecycle: subscribe → sweep → re-subscribe.

Locks in the telegram-feed-iy7 fix across four components against a real
Postgres: a channel stays in the catalog after the last subscriber leaves,
the sweep parks it as `dormant` without leaving it, and a fresh subscribe
reactivates it through the join queue. Telegram is a FakeTelethonClient.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.pagination import CatalogCursor
from ingester import join_worker, refcount_sweep
from ingester.live import _to_marked_chat_id
from shared.auth.jwt import encode_access
from shared.models import (
    Channel,
    ChannelJoinQueue,
    ChannelSubscription,
    Post,
    UserSource,
)
from shared.repositories.channel_catalog import list_catalog_available
from tests.integration._fakes.fake_telethon import (
    FakeTelethonClient,
    make_fake_message,
)

SECRET = "x" * 32


class _Settings:
    """Minimal settings stand-in. The photo/video download path that reads
    these fields is never reached by the text-only message fixtures."""

    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


def _auth(user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"
    }


async def _catalog_ids(session_factory, *, user_id: int) -> list[int]:
    async with session_factory() as s:
        rows = await list_catalog_available(
            s, user_id=user_id, cursor=CatalogCursor.initial_available(),
            limit=50, q=None,
        )
    return [r.channel_id for r in rows]


async def _subscription(session_factory, channel_id: int) -> ChannelSubscription:
    async with session_factory() as s:
        sub = await s.get(ChannelSubscription, channel_id)
    assert sub is not None
    return sub


async def _post_count(session_factory, channel_id: int) -> int:
    async with session_factory() as s:
        return (await s.execute(
            select(func.count()).select_from(Post).where(Post.channel_id == channel_id)
        )).scalar_one()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_lifecycle_subscribe_sweep_resubscribe(
    pg_container, async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=7001)
    tg_chat_id = 770001
    username = "lifecyclechan"

    # Step 1 — an active channel with one subscriber.
    ch = Channel(
        tg_chat_id=tg_chat_id, username=username, title="Lifecycle", posts_count=3,
    )
    db_session.add(ch)
    await db_session.commit()
    channel_id = ch.id
    db_session.add(
        ChannelSubscription(channel_id=channel_id, status="active", ref_count=1)
    )
    db_session.add(UserSource(user_id=uid, channel_id=channel_id))
    await db_session.commit()

    engine = create_async_engine(
        pg_container["async_url"], pool_pre_ping=True, future=True
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        assert channel_id in await _catalog_ids(session_factory, user_id=uid)

        # Step 2 — the last subscriber unsubscribes → ref_count hits 0.
        r = await async_client.delete(f"/sources/{channel_id}", headers=_auth(uid))
        assert r.status_code == 204, r.text
        assert (await _subscription(session_factory, channel_id)).ref_count == 0

        # Step 3 — the sweep parks the channel as dormant (no physical leave)
        # and drops it from the live chat_map.
        chat_map = {_to_marked_chat_id(tg_chat_id): channel_id}
        await refcount_sweep._sweep_once(session_factory, chat_map=chat_map)

        sub = await _subscription(session_factory, channel_id)
        assert sub.status == "dormant"
        assert chat_map == {}
        # Bug-1: a dormant channel is still listed in the catalog.
        assert channel_id in await _catalog_ids(session_factory, user_id=uid)

        # Step 4 — re-subscribe via the catalog button → queued, not 404.
        r = await async_client.post(f"/sources/{channel_id}", headers=_auth(uid))
        assert r.status_code == 202, r.text
        queue_id = r.json()["queue_id"]
        async with session_factory() as s:
            qrow = await s.get(ChannelJoinQueue, queue_id)
            assert qrow.kind == "public_username"
            assert qrow.channel_username == username
            assert qrow.status == "pending"

        # Step 5 — the join worker reactivates the channel and backfills posts.
        fake = FakeTelethonClient()
        fake.entities[username] = SimpleNamespace(
            id=tg_chat_id, username=username, title="Lifecycle",
        )
        fake.catchup_messages[tg_chat_id] = [
            make_fake_message(id=1001, text="post one"),
            make_fake_message(id=1002, text="post two"),
        ]
        await join_worker._handle_one_pending(
            fake, session_factory,
            minio_client=MagicMock(), bucket="media", settings=_Settings(),
            chat_map=chat_map,
        )

        sub = await _subscription(session_factory, channel_id)
        assert sub.status == "active"
        assert sub.ref_count == 1
        async with session_factory() as s:
            qrow = await s.get(ChannelJoinQueue, queue_id)
            assert qrow.status == "done"
        assert await _post_count(session_factory, channel_id) == 2
        assert channel_id in await _catalog_ids(session_factory, user_id=uid)
        # Live updates resume: the channel is back in the chat_map.
        assert chat_map == {_to_marked_chat_id(tg_chat_id): channel_id}
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_backfill_dedup_no_duplicate_posts(
    pg_container, db_session, seed_user
) -> None:
    """Re-running the backfill over the identical backlog inserts no
    duplicate posts — upsert_post's ON CONFLICT (channel_id, tg_message_id)
    already guarantees this; the test fixes the contract."""
    await seed_user(tg_user_id=7002)
    tg_chat_id = 770002
    ch = Channel(
        tg_chat_id=tg_chat_id, username="dedupbackfill", title="DedupBackfill",
        posts_count=3,
    )
    db_session.add(ch)
    await db_session.commit()
    channel_id = ch.id
    db_session.add(
        ChannelSubscription(
            channel_id=channel_id, status="pending_backfill", ref_count=1
        )
    )
    await db_session.commit()

    fake = FakeTelethonClient()
    entity = SimpleNamespace(id=tg_chat_id, username="dedupbackfill", title="DedupBackfill")
    fake.catchup_messages[tg_chat_id] = [
        make_fake_message(id=2001, text="msg one"),
        make_fake_message(id=2002, text="msg two"),
        make_fake_message(id=2003, text="msg three"),
    ]

    engine = create_async_engine(
        pg_container["async_url"], pool_pre_ping=True, future=True
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await join_worker._backfill_channel(
            fake, session_factory, MagicMock(), entity, channel_id,
            limit=50, bucket="media", settings=_Settings(),
        )
        assert await _post_count(session_factory, channel_id) == 3

        # Second pass over the identical backlog must add nothing.
        await join_worker._backfill_channel(
            fake, session_factory, MagicMock(), entity, channel_id,
            limit=50, bucket="media", settings=_Settings(),
        )
        assert await _post_count(session_factory, channel_id) == 3
    finally:
        await engine.dispose()
