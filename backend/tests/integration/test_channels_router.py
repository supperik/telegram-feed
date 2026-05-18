from unittest.mock import MagicMock

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"
    }


def _fake_minio_client(payload: bytes) -> MagicMock:
    response = MagicMock()
    response.stream = MagicMock(return_value=iter([payload]))
    response.close = MagicMock()
    response.release_conn = MagicMock()
    client = MagicMock()
    client.get_object = MagicMock(return_value=response)
    return client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_photo_streams_bytes_from_minio(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    uid = await seed_user(tg_user_id=70)
    ch = Channel(
        tg_chat_id=140001,
        username="a",
        title="A",
        photo_storage_key="channel_photos/123.jpg",
    )
    db_session.add(ch)
    await db_session.commit()

    payload = b"\xff\xd8\xff\xe0avatarbytes"
    fake = _fake_minio_client(payload)
    monkeypatch.setattr("api.routers.channels.make_storage_client", lambda: fake)

    r = await async_client.get(f"/channels/{ch.id}/photo", headers=_auth(uid))
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == payload
    fake.get_object.assert_called_once_with("media", "channel_photos/123.jpg")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_photo_returns_404_when_no_storage_key(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    uid = await seed_user(tg_user_id=71)
    ch = Channel(
        tg_chat_id=140002,
        username="b",
        title="B",
        photo_storage_key=None,
    )
    db_session.add(ch)
    await db_session.commit()

    fake = _fake_minio_client(b"")
    monkeypatch.setattr("api.routers.channels.make_storage_client", lambda: fake)

    r = await async_client.get(f"/channels/{ch.id}/photo", headers=_auth(uid))
    assert r.status_code == 404
    fake.get_object.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_photo_accepts_jwt_via_query_token(
    async_client, db_session, seed_user, monkeypatch
) -> None:
    """`<img src="/api/channels/{id}/photo">` can't send Authorization;
    the JWT travels through ?token=… instead."""
    uid = await seed_user(tg_user_id=72)
    ch = Channel(
        tg_chat_id=140003,
        username="c",
        title="C",
        photo_storage_key="channel_photos/72.jpg",
    )
    db_session.add(ch)
    await db_session.commit()

    payload = b"\xff\xd8\xff\xe0querytoken"
    fake = _fake_minio_client(payload)
    monkeypatch.setattr("api.routers.channels.make_storage_client", lambda: fake)

    token = encode_access(user_id=uid, secret=SECRET, ttl_seconds=60)
    r = await async_client.get(f"/channels/{ch.id}/photo?token={token}")

    assert r.status_code == 200
    assert r.content == payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_photo_returns_401_without_token(
    async_client, db_session, seed_user
) -> None:
    await seed_user(tg_user_id=73)
    ch = Channel(
        tg_chat_id=140004,
        username="d",
        title="D",
        photo_storage_key="channel_photos/73.jpg",
    )
    db_session.add(ch)
    await db_session.commit()

    r = await async_client.get(f"/channels/{ch.id}/photo")
    assert r.status_code == 401
