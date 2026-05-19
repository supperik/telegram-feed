"""End-to-end integration tests for the ingester pipeline.

Covers live NewMessage + restart-catchup flow against real Postgres and
real MinIO (testcontainers) using a FakeTelethonClient that emits
synthetic NewMessage events. Album / sweep / full-main() flow is
out of scope — see docs/superpowers/specs/2026-05-19-ingester-e2e-design.md.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_fake_telethon_dispatches_new_message_to_handler():
    """Sanity: after add_event_handler+emit_new_message, the registered
    coroutine receives the synthetic event. This is the smallest contract
    that the live e2e test relies on."""
    from telethon import events

    from tests.integration._fakes.fake_telethon import (
        FakeTelethonClient,
        make_fake_message,
    )

    fake = FakeTelethonClient()
    received: list = []

    async def handler(event):
        received.append(event)

    fake.add_event_handler(handler, events.NewMessage())
    msg = make_fake_message(id=1, text="hi")
    await fake.emit_new_message(msg, chat_id=-1001234567890)

    assert len(received) == 1
    assert received[0].chat_id == -1001234567890
    assert received[0].message is msg


@pytest.mark.integration
def test_minio_container_smoke(minio_container):
    """Fixture provides {endpoint, access_key, secret_key} and the
    container is healthy enough that a bucket can be created."""
    from minio import Minio

    client = Minio(
        minio_container["endpoint"],
        access_key=minio_container["access_key"],
        secret_key=minio_container["secret_key"],
        secure=False,
    )
    bucket = "ingester-e2e-smoke"
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    assert client.bucket_exists(bucket)


def _configure_minio_env(monkeypatch, minio_container) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", minio_container["endpoint"])
    monkeypatch.setenv("MINIO_ACCESS_KEY", minio_container["access_key"])
    monkeypatch.setenv("MINIO_SECRET_KEY", minio_container["secret_key"])


def _configure_postgres_env(monkeypatch, pg_container) -> None:
    monkeypatch.setenv("POSTGRES_USER", pg_container["user"])
    monkeypatch.setenv("POSTGRES_PASSWORD", pg_container["password"])
    monkeypatch.setenv("POSTGRES_DB", pg_container["db"])
    monkeypatch.setenv("POSTGRES_HOST", pg_container["host"])
    monkeypatch.setenv("POSTGRES_PORT", str(pg_container["port"]))


def _build_settings(monkeypatch, pg_container, redis_container, minio_container):
    """Apply env + reset get_settings cache so live/photos see test endpoints."""
    from shared.config import get_settings

    _configure_postgres_env(monkeypatch, pg_container)
    monkeypatch.setenv("REDIS_HOST", redis_container["host"])
    monkeypatch.setenv("REDIS_PORT", str(redis_container["port"]))
    _configure_minio_env(monkeypatch, minio_container)
    monkeypatch.setenv("API_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("TG_BOT_TOKEN", "1234:test-bot-token")
    get_settings.cache_clear()
    return get_settings()


async def _seed_active_channel(
    db_session,
    *,
    tg_chat_id: int,
    title: str = "Test Channel",
    username: str | None = None,
) -> int:
    """Insert Channel + active ChannelSubscription. Returns Channel.id."""
    from shared.models import Channel, ChannelSubscription

    channel = Channel(tg_chat_id=tg_chat_id, title=title, username=username)
    db_session.add(channel)
    await db_session.commit()
    await db_session.refresh(channel)

    sub = ChannelSubscription(channel_id=channel.id, status="active", ref_count=1)
    db_session.add(sub)
    await db_session.commit()
    return channel.id


@pytest.mark.integration
async def test_live_post_with_photo_e2e(
    pg_container, redis_container, minio_container, db_session, monkeypatch
):
    """Full live path: subscribe → emit NewMessage → assert Post, Media.storage_key, MinIO bytes."""
    from minio import Minio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from telethon.tl.types import PeerChannel
    from telethon.utils import get_peer_id

    from ingester.live import subscribe_to_active_channels
    from shared.models import Media, Post
    from shared.storage import ensure_bucket
    from tests.integration._fakes.fake_telethon import (
        FakeTelethonClient,
        make_fake_message,
        make_fake_photo,
    )

    settings = _build_settings(monkeypatch, pg_container, redis_container, minio_container)
    positive_chat_id = 1234567890
    channel_id = await _seed_active_channel(
        db_session, tg_chat_id=positive_chat_id, title="Live e2e", username="live_e2e"
    )

    minio_client = Minio(
        minio_container["endpoint"],
        access_key=minio_container["access_key"],
        secret_key=minio_container["secret_key"],
        secure=False,
    )
    ensure_bucket(minio_client, settings.minio_bucket)

    fake_photo_id = 999
    fake_payload = b"jpeg-bytes-for-msg-42"
    fake = FakeTelethonClient()
    fake.download_payloads[fake_photo_id] = fake_payload

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        chat_map = await subscribe_to_active_channels(
            fake,
            session_factory,
            minio_client=minio_client,
            bucket=settings.minio_bucket,
            settings=settings,
        )
        marked_id = get_peer_id(PeerChannel(positive_chat_id))
        assert marked_id in chat_map

        msg = make_fake_message(
            id=42,
            text="hello e2e",
            photo=make_fake_photo(photo_id=fake_photo_id),
        )
        await fake.emit_new_message(msg, chat_id=marked_id)

        async with session_factory() as s:
            posts = (
                await s.execute(select(Post).where(Post.channel_id == channel_id))
            ).scalars().all()
            assert len(posts) == 1
            assert posts[0].tg_message_id == 42
            assert posts[0].text == "hello e2e"

            medias = (
                await s.execute(select(Media).where(Media.post_id == posts[0].id))
            ).scalars().all()
            assert len(medias) == 1
            expected_key = f"photos/{channel_id}/42_{fake_photo_id}.jpg"
            assert medias[0].storage_key == expected_key
            assert medias[0].type == "photo"
            assert medias[0].tg_file_id == str(fake_photo_id)
    finally:
        await engine.dispose()

    obj = minio_client.get_object(settings.minio_bucket, expected_key)
    try:
        data = obj.read()
    finally:
        obj.close()
        obj.release_conn()
    assert data == fake_payload


@pytest.mark.integration
async def test_catchup_with_backlog_e2e(
    pg_container, redis_container, minio_container, db_session, monkeypatch
):
    """Restart catchup: 3 backlog messages → 3 Posts + 3 Media + 3 MinIO blobs.

    Second pass through catchup_channels with the same backlog must be
    idempotent (max(tg_message_id) becomes the new min_id; iter_messages
    yields nothing past it)."""
    from minio import Minio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from ingester.live import catchup_channels
    from shared.models import Media, Post
    from shared.storage import ensure_bucket
    from tests.integration._fakes.fake_telethon import (
        FakeTelethonClient,
        make_fake_message,
        make_fake_photo,
    )

    settings = _build_settings(monkeypatch, pg_container, redis_container, minio_container)
    positive_chat_id = 9876543210
    channel_id = await _seed_active_channel(
        db_session, tg_chat_id=positive_chat_id, title="Catchup e2e", username="catchup_e2e"
    )

    minio_client = Minio(
        minio_container["endpoint"],
        access_key=minio_container["access_key"],
        secret_key=minio_container["secret_key"],
        secure=False,
    )
    ensure_bucket(minio_client, settings.minio_bucket)

    # Three backlog messages with photos; payloads keyed by photo.id.
    backlog_specs = [
        (10, 1010, b"payload-10"),
        (11, 1011, b"payload-11"),
        (12, 1012, b"payload-12"),
    ]
    backlog_msgs = [
        make_fake_message(id=msg_id, text=f"msg-{msg_id}", photo=make_fake_photo(photo_id=ph_id))
        for msg_id, ph_id, _ in backlog_specs
    ]

    fake = FakeTelethonClient()
    fake.catchup_messages[positive_chat_id] = backlog_msgs
    fake.download_payloads = {ph_id: payload for _, ph_id, payload in backlog_specs}

    engine = create_async_engine(pg_container["async_url"], pool_pre_ping=True, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await catchup_channels(
            fake,
            session_factory,
            minio_client,
            bucket=settings.minio_bucket,
            settings=settings,
            limit=200,
        )

        async with session_factory() as s:
            posts = (
                await s.execute(
                    select(Post).where(Post.channel_id == channel_id).order_by(Post.tg_message_id)
                )
            ).scalars().all()
            assert [p.tg_message_id for p in posts] == [10, 11, 12]

            medias = (
                await s.execute(
                    select(Media).where(Media.post_id.in_([p.id for p in posts]))
                )
            ).scalars().all()
            assert len(medias) == 3
            assert all(m.storage_key is not None for m in medias)
            assert all(m.type == "photo" for m in medias)

        for msg_id, ph_id, expected_payload in backlog_specs:
            key = f"photos/{channel_id}/{msg_id}_{ph_id}.jpg"
            obj = minio_client.get_object(settings.minio_bucket, key)
            try:
                assert obj.read() == expected_payload
            finally:
                obj.close()
                obj.release_conn()

        # Idempotency: second pass over the same backlog must add nothing.
        await catchup_channels(
            fake,
            session_factory,
            minio_client,
            bucket=settings.minio_bucket,
            settings=settings,
            limit=200,
        )
        async with session_factory() as s:
            posts_after = (
                await s.execute(select(Post).where(Post.channel_id == channel_id))
            ).scalars().all()
            assert len(posts_after) == 3
    finally:
        await engine.dispose()
