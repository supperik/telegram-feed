import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel, UserHiddenChannel, UserSource


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_hidden_returns_subscribed_hidden(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=61)
    ch = Channel(tg_chat_id=61001, username="hid_one", title="Hidden One")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=uid, channel_id=ch.id))
    db_session.add(UserHiddenChannel(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    r = await async_client.get("/sources/hidden", headers=_auth(uid))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["channel"]["username"] == "hid_one"
    assert items[0]["channel"]["title"] == "Hidden One"
    assert items[0]["hidden_at"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_hidden_excludes_unsubscribed(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=62)
    ch = Channel(tg_chat_id=62001, username="orphan", title="Orphan")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserHiddenChannel(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    r = await async_client.get("/sources/hidden", headers=_auth(uid))
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_hidden_isolates_users(
    async_client, db_session, seed_user
) -> None:
    uid_a = await seed_user(tg_user_id=63)
    uid_b = await seed_user(tg_user_id=64)
    ch = Channel(tg_chat_id=63001, username="iso2", title="Iso2")
    db_session.add(ch)
    await db_session.commit()
    db_session.add_all([
        UserSource(user_id=uid_a, channel_id=ch.id),
        UserSource(user_id=uid_b, channel_id=ch.id),
        UserHiddenChannel(user_id=uid_a, channel_id=ch.id),
    ])
    await db_session.commit()

    r_a = await async_client.get("/sources/hidden", headers=_auth(uid_a))
    r_b = await async_client.get("/sources/hidden", headers=_auth(uid_b))
    assert [i["channel"]["id"] for i in r_a.json()["items"]] == [ch.id]
    assert r_b.json()["items"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_hide_unhides_and_is_idempotent(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=65)
    ch = Channel(tg_chat_id=65001, username="uh_api", title="UH API")
    db_session.add(ch)
    await db_session.commit()
    db_session.add_all([
        UserSource(user_id=uid, channel_id=ch.id),
        UserHiddenChannel(user_id=uid, channel_id=ch.id),
    ])
    await db_session.commit()

    channel_id = ch.id

    r = await async_client.delete(f"/sources/{channel_id}/hide", headers=_auth(uid))
    assert r.status_code == 204, r.text
    db_session.expire_all()
    assert await db_session.get(UserHiddenChannel, (uid, channel_id)) is None

    # Idempotent second DELETE.
    r2 = await async_client.delete(f"/sources/{channel_id}/hide", headers=_auth(uid))
    assert r2.status_code == 204, r2.text
