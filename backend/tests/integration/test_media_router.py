from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel, Media, Post


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_media_redirects_to_presigned_url(
    async_client, db_session, seed_user, monkeypatch
) -> None:
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

    fake = MagicMock()
    fake.presigned_get_object.return_value = "https://minio.example/photos/1/1.jpg?sig=zzz"
    monkeypatch.setattr("api.routers.media.make_storage_client", lambda: fake)

    r = await async_client.get(f"/media/{media.id}", headers=_auth(uid), follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://minio.example/photos/1/1.jpg?sig=zzz"
