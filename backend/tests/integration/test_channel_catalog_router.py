import pytest

from shared.auth.jwt import encode_access
from shared.models import (
    Channel,
    ChannelSubscription,
    UserCatalogHiddenChannel,
    UserSource,
)

SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"
    }


async def _seed_active_channel(
    db_session, *, tg_chat_id: int, username: str | None, title: str,
    posts_count: int = 1, ref_count: int = 1, banned: bool = False,
) -> Channel:
    ch = Channel(
        tg_chat_id=tg_chat_id, username=username, title=title,
        posts_count=posts_count, banned=banned,
    )
    db_session.add(ch)
    await db_session.commit()
    db_session.add(
        ChannelSubscription(channel_id=ch.id, status="active", ref_count=ref_count)
    )
    await db_session.commit()
    return ch


# Catalog-router tests share the same global DB with other integration tests,
# so wipe rows from the three input tables before each test to keep assertions
# tight. Channels & posts are left alone — they don't affect the assertions
# below (we filter by ChannelSubscription which we wipe, so stray channel rows
# from other suites can't sneak in).
@pytest.fixture(autouse=True)
async def _reset_catalog_router_inputs(db_session):
    from sqlalchemy import delete as sql_delete
    await db_session.execute(sql_delete(UserCatalogHiddenChannel))
    await db_session.execute(sql_delete(UserSource))
    await db_session.execute(sql_delete(ChannelSubscription))
    await db_session.commit()
    yield


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_default_view_available(async_client, db_session, seed_user):
    uid = await seed_user(tg_user_id=301)
    ch1 = await _seed_active_channel(
        db_session, tg_chat_id=10001, username="cat_router_aaa", title="AAA", posts_count=10,
    )
    ch2 = await _seed_active_channel(
        db_session, tg_chat_id=10002, username="cat_router_bbb", title="BBB", posts_count=5,
    )
    r = await async_client.get("/channels/catalog", headers=_auth(uid))
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [i["channel"]["id"] for i in body["items"]]
    assert ids == [ch1.id, ch2.id]
    assert body["items"][0]["subscribers_count"] == 1
    assert body["items"][0]["is_subscribed"] is False
    assert body["items"][0]["is_hidden_from_catalog"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_pagination(async_client, db_session, seed_user):
    uid = await seed_user(tg_user_id=302)
    for i in range(3):
        await _seed_active_channel(
            db_session, tg_chat_id=11000 + i,
            username=f"cat_router_p{i}", title=f"P{i}", posts_count=10 - i,
        )
    r1 = await async_client.get("/channels/catalog?limit=2", headers=_auth(uid))
    body1 = r1.json()
    assert len(body1["items"]) == 2
    assert body1["next_cursor"] is not None

    r2 = await async_client.get(
        f"/channels/catalog?limit=2&cursor={body1['next_cursor']}",
        headers=_auth(uid),
    )
    body2 = r2.json()
    assert len(body2["items"]) == 1
    seen = {i["channel"]["id"] for i in body1["items"] + body2["items"]}
    assert len(seen) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_q_filter(async_client, db_session, seed_user):
    uid = await seed_user(tg_user_id=303)
    ch = await _seed_active_channel(
        db_session, tg_chat_id=12001, username="cat_router_meduzaproject", title="Meduza",
        posts_count=1,
    )
    await _seed_active_channel(
        db_session, tg_chat_id=12002, username="cat_router_other", title="Other", posts_count=1,
    )
    r = await async_client.get("/channels/catalog?q=medU", headers=_auth(uid))
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["channel"]["id"] == ch.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_view_hidden(async_client, db_session, seed_user):
    uid = await seed_user(tg_user_id=304)
    ch = await _seed_active_channel(
        db_session, tg_chat_id=13001, username="cat_router_h", title="H", posts_count=1,
    )
    db_session.add(UserCatalogHiddenChannel(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    r_avail = await async_client.get("/channels/catalog", headers=_auth(uid))
    assert r_avail.json()["items"] == []

    r_hidden = await async_client.get(
        "/channels/catalog?view=hidden", headers=_auth(uid)
    )
    items = r_hidden.json()["items"]
    assert len(items) == 1
    assert items[0]["channel"]["id"] == ch.id
    assert items[0]["is_hidden_from_catalog"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_is_subscribed_flag(async_client, db_session, seed_user):
    uid = await seed_user(tg_user_id=305)
    ch = await _seed_active_channel(
        db_session, tg_chat_id=14001, username="cat_router_s", title="S", posts_count=1,
    )
    db_session.add(UserSource(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    r = await async_client.get("/channels/catalog", headers=_auth(uid))
    items = r.json()["items"]
    assert items[0]["is_subscribed"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_bad_cursor_400(async_client, seed_user):
    uid = await seed_user(tg_user_id=306)
    r = await async_client.get("/channels/catalog?cursor=not-base64", headers=_auth(uid))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_cursor"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalog_rejects_mismatched_cursor_view(
    async_client, db_session, seed_user,
):
    from api.pagination import CatalogCursor

    uid = await seed_user(tg_user_id=307)
    cursor = CatalogCursor.initial_hidden().encode()
    r = await async_client.get(
        f"/channels/catalog?view=available&cursor={cursor}", headers=_auth(uid)
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_cursor"
