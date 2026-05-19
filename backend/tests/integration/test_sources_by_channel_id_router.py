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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_subscribes_and_clears_hidden(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=201)
    ch = Channel(tg_chat_id=9001, username="cat_byid", title="ById", posts_count=1)
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=0))
    db_session.add(UserCatalogHiddenChannel(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "subscribed"
    assert body["channel"]["id"] == ch.id

    assert (await db_session.get(UserSource, (uid, ch.id))) is not None
    assert (await db_session.get(UserCatalogHiddenChannel, (uid, ch.id))) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_404_for_missing(async_client, seed_user) -> None:
    uid = await seed_user(tg_user_id=202)
    r = await async_client.post("/sources/999999", headers=_auth(uid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "channel_not_found"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_404_for_inactive(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=203)
    ch = Channel(tg_chat_id=9002, username="cat_ina", title="Ina", posts_count=1)
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="failed", ref_count=1))
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "channel_not_available"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_403_for_banned(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=204)
    ch = Channel(
        tg_chat_id=9003, username="cat_ban", title="Ban", posts_count=1, banned=True,
    )
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "channel_banned"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_idempotent(
    async_client, db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=205)
    ch = Channel(tg_chat_id=9004, username="cat_idemp", title="Idemp", posts_count=1)
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    await db_session.commit()

    r1 = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    r2 = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["channel"]["id"] == r2.json()["channel"]["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_status_route_not_shadowed_by_by_id(async_client, seed_user) -> None:
    uid = await seed_user(tg_user_id=210)
    r = await async_client.get("/sources/queue/999", headers=_auth(uid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "queue_not_found"
