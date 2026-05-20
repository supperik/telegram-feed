from datetime import datetime, timedelta, timezone

import pytest

from shared.auth.jwt import encode_access
from shared.models import (
    Channel,
    Post,
    UserHiddenPost,
    UserSavedPost,
    UserSource,
)


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unhide_post(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=55)
    ch = Channel(tg_chat_id=110005, username="uh", title="UH")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    db_session.add(UserHiddenPost(user_id=uid, post_id=p.id))
    await db_session.commit()

    r = await async_client.delete(f"/posts/{p.id}/hide", headers=_auth(uid))
    assert r.status_code == 204
    assert await db_session.get(UserHiddenPost, (uid, p.id)) is None

    # Idempotent — second delete on missing row still 204.
    r = await async_client.delete(f"/posts/{p.id}/hide", headers=_auth(uid))
    assert r.status_code == 204


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_saved_posts_returns_newest_first(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=56)
    ch = Channel(tg_chat_id=110006, username="ls", title="LS")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=uid, channel_id=ch.id))
    await db_session.commit()
    base = datetime(2026, 4, 1, tzinfo=timezone.utc)
    p1 = Post(channel_id=ch.id, tg_message_id=1, posted_at=base)
    p2 = Post(channel_id=ch.id, tg_message_id=2, posted_at=base + timedelta(seconds=1))
    db_session.add_all([p1, p2])
    await db_session.commit()
    db_session.add(UserSavedPost(user_id=uid, post_id=p1.id, saved_at=base))
    await db_session.commit()
    db_session.add(UserSavedPost(user_id=uid, post_id=p2.id, saved_at=base + timedelta(minutes=1)))
    await db_session.commit()

    r = await async_client.get("/posts/saved", headers=_auth(uid))
    assert r.status_code == 200
    body = r.json()
    assert [p["tg_message_id"] for p in body["posts"]] == [2, 1]
    assert all(p["is_saved"] is True for p in body["posts"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_saved_posts_paginates(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=57)
    ch = Channel(tg_chat_id=110007, username="lsp", title="LSP")
    db_session.add(ch)
    await db_session.commit()
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    for i in range(3):
        p = Post(channel_id=ch.id, tg_message_id=100 + i, posted_at=base + timedelta(minutes=i))
        db_session.add(p)
        await db_session.commit()
        db_session.add(
            UserSavedPost(user_id=uid, post_id=p.id, saved_at=base + timedelta(minutes=i))
        )
        await db_session.commit()

    r = await async_client.get("/posts/saved?limit=2", headers=_auth(uid))
    assert r.status_code == 200
    body = r.json()
    assert len(body["posts"]) == 2
    assert body["next_cursor"]

    r2 = await async_client.get(
        f"/posts/saved?limit=2&cursor={body['next_cursor']}", headers=_auth(uid)
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["posts"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_hidden_posts(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=58)
    ch = Channel(tg_chat_id=110008, username="lh", title="LH")
    db_session.add(ch)
    await db_session.commit()
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    p1 = Post(channel_id=ch.id, tg_message_id=1, posted_at=base)
    p2 = Post(channel_id=ch.id, tg_message_id=2, posted_at=base + timedelta(seconds=1))
    db_session.add_all([p1, p2])
    await db_session.commit()
    db_session.add(UserHiddenPost(user_id=uid, post_id=p1.id, hidden_at=base))
    await db_session.commit()
    db_session.add(
        UserHiddenPost(user_id=uid, post_id=p2.id, hidden_at=base + timedelta(minutes=1))
    )
    db_session.add(UserSavedPost(user_id=uid, post_id=p1.id))
    await db_session.commit()

    r = await async_client.get("/posts/hidden", headers=_auth(uid))
    assert r.status_code == 200
    body = r.json()
    assert [p["tg_message_id"] for p in body["posts"]] == [2, 1]
    by_id = {p["tg_message_id"]: p for p in body["posts"]}
    assert by_id[1]["is_saved"] is True
    assert by_id[2]["is_saved"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_saved_bad_cursor_returns_400(async_client, seed_user) -> None:
    uid = await seed_user(tg_user_id=59)
    r = await async_client.get("/posts/saved?cursor=not-base64-at-all!!", headers=_auth(uid))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_cursor"
