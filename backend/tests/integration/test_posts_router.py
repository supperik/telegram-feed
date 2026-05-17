from datetime import datetime, timezone

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel, Post, UserHiddenPost, UserSavedPost


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_and_unsave_post(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=51)
    ch = Channel(tg_chat_id=110001, username="z", title="Z")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()

    r = await async_client.post(f"/posts/{p.id}/save", headers=_auth(uid))
    assert r.status_code == 204
    assert await db_session.get(UserSavedPost, (uid, p.id)) is not None

    r = await async_client.delete(f"/posts/{p.id}/save", headers=_auth(uid))
    assert r.status_code == 204
    assert await db_session.get(UserSavedPost, (uid, p.id)) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hide_post(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=52)
    ch = Channel(tg_chat_id=110002, username="zz", title="ZZ")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()

    r = await async_client.post(f"/posts/{p.id}/hide", headers=_auth(uid))
    assert r.status_code == 204
    assert await db_session.get(UserHiddenPost, (uid, p.id)) is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_unknown_post_returns_404(async_client, seed_user) -> None:
    uid = await seed_user(tg_user_id=53)
    r = await async_client.post("/posts/999999999/save", headers=_auth(uid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "post_not_found"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hide_unknown_post_returns_404(async_client, seed_user) -> None:
    uid = await seed_user(tg_user_id=54)
    r = await async_client.post("/posts/999999999/hide", headers=_auth(uid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "post_not_found"
