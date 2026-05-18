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
