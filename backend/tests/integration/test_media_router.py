from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel, Media, Post


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


def _fake_minio_client(payload: bytes) -> MagicMock:
    """Build a MagicMock that mimics minio.Minio.get_object — used by the
    streaming media endpoint. The .stream() method yields the payload in
    one chunk; close()/release_conn() are no-ops."""
    response = MagicMock()
    response.stream = MagicMock(return_value=iter([payload]))
    response.close = MagicMock()
    response.release_conn = MagicMock()
    client = MagicMock()
    client.get_object = MagicMock(return_value=response)
    return client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_streams_bytes_from_minio(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    """GET /media/{id} streams the file from MinIO through the API. We
    cannot 302-redirect to MinIO because its endpoint is the internal
    docker hostname (minio:9000) — unreachable from the browser."""
    uid = await seed_user(tg_user_id=61)
    ch = Channel(tg_chat_id=120001, username="m", title="M")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(post_id=p.id, type="photo", storage_key="photos/1/1.jpg", position=0)
    db_session.add(media)
    await db_session.commit()

    payload = b"\xff\xd8\xff\xe0fakephotobytes"
    fake = _fake_minio_client(payload)
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    r = await async_client.get(f"/media/{media.id}", headers=_auth(uid))
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == payload
    # Long-lived cache — storage_key contains immutable tg msg+photo id.
    assert "max-age" in r.headers.get("cache-control", "").lower()
    # MinIO get_object was called with bucket+key from the row.
    fake.get_object.assert_called_once_with("media", "photos/1/1.jpg")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_returns_404_when_storage_key_missing(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    uid = await seed_user(tg_user_id=62)
    ch = Channel(tg_chat_id=120002, username="n", title="N")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=2, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(post_id=p.id, type="photo", storage_key=None, position=0)
    db_session.add(media)
    await db_session.commit()

    fake = _fake_minio_client(b"")
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    r = await async_client.get(f"/media/{media.id}", headers=_auth(uid))
    assert r.status_code == 404
    fake.get_object.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_accepts_jwt_via_query_token(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    """Native <img src="/api/media/{id}"> can't send Authorization header,
    so the endpoint must accept the JWT via ?token=... query param.
    Regression: telegram-feed-xk8."""
    uid = await seed_user(tg_user_id=63)
    ch = Channel(tg_chat_id=120003, username="q", title="Q")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=3, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(post_id=p.id, type="photo", storage_key="photos/3/3.jpg", position=0)
    db_session.add(media)
    await db_session.commit()

    payload = b"\xff\xd8\xff\xe0querytokenbytes"
    fake = _fake_minio_client(payload)
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    token = encode_access(user_id=uid, secret=SECRET, ttl_seconds=60)
    # No Authorization header — token in query only.
    r = await async_client.get(f"/media/{media.id}?token={token}")

    assert r.status_code == 200
    assert r.content == payload
    assert r.headers["content-type"] == "image/jpeg"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_returns_401_without_any_token(
    async_client, db_session, seed_user
) -> None:
    """No header and no query token → unauthenticated."""
    uid = await seed_user(tg_user_id=64)
    ch = Channel(tg_chat_id=120004, username="z", title="Z")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=4, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(post_id=p.id, type="photo", storage_key="photos/4/4.jpg", position=0)
    db_session.add(media)
    await db_session.commit()

    r = await async_client.get(f"/media/{media.id}")
    assert r.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_media_video_returns_mp4_when_video_storage_key_set(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    """GET /media/{id}/video streams the MinIO object at video_storage_key
    with Content-Type: video/mp4."""
    uid = await seed_user(tg_user_id=9001)
    ch = Channel(tg_chat_id=120010, username="v1", title="V1")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=10, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(
        post_id=p.id,
        type="video",
        storage_key="video_thumbs/10/10.jpg",
        video_storage_key="videos/10/10.mp4",
        position=0,
    )
    db_session.add(media)
    await db_session.commit()

    payload = b"\x00\x00\x00\x18ftypmp42fakevideobytes"
    fake = _fake_minio_client(payload)
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    r = await async_client.get(f"/media/{media.id}/video", headers=_auth(uid))
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert r.content == payload
    assert "max-age" in r.headers.get("cache-control", "").lower()
    fake.get_object.assert_called_once_with("media", "videos/10/10.mp4")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_media_video_404_when_no_video_storage_key(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    """Video media with video_storage_key=None (e.g. capped by size) → 404."""
    uid = await seed_user(tg_user_id=9002)
    ch = Channel(tg_chat_id=120011, username="v2", title="V2")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=11, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(
        post_id=p.id,
        type="video",
        storage_key="video_thumbs/11/11.jpg",
        video_storage_key=None,
        position=0,
    )
    db_session.add(media)
    await db_session.commit()

    fake = _fake_minio_client(b"")
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    r = await async_client.get(f"/media/{media.id}/video", headers=_auth(uid))
    assert r.status_code == 404
    fake.get_object.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_media_video_404_for_photo_media(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    """A photo row (even with a storage_key) is not a video → 404 from the
    /video endpoint even if the caller is authenticated."""
    uid = await seed_user(tg_user_id=9003)
    ch = Channel(tg_chat_id=120012, username="v3", title="V3")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=12, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    # Photo media: type=photo, no video_storage_key. Even if someone set
    # video_storage_key on a photo row by mistake, type guard wins.
    media = Media(
        post_id=p.id,
        type="photo",
        storage_key="photos/12/12.jpg",
        video_storage_key="videos/12/12.mp4",
        position=0,
    )
    db_session.add(media)
    await db_session.commit()

    fake = _fake_minio_client(b"")
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    r = await async_client.get(f"/media/{media.id}/video", headers=_auth(uid))
    assert r.status_code == 404
    fake.get_object.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_media_video_401_without_token(
    async_client, db_session, seed_user
) -> None:
    """No auth → 401 (same dependency as /media/{id})."""
    uid = await seed_user(tg_user_id=9004)
    ch = Channel(tg_chat_id=120013, username="v4", title="V4")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=13, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    media = Media(
        post_id=p.id,
        type="video",
        storage_key="video_thumbs/13/13.jpg",
        video_storage_key="videos/13/13.mp4",
        position=0,
    )
    db_session.add(media)
    await db_session.commit()

    r = await async_client.get(f"/media/{media.id}/video")
    assert r.status_code == 401
