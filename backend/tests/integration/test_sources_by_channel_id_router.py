import pytest
from sqlalchemy import text

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
async def test_post_sources_by_id_queues_dormant_public(
    async_client, db_session, seed_user
) -> None:
    """A catalog re-subscribe (POST /sources/{id}) to a dormant public
    channel queues a public-username join instead of returning 404
    (telegram-feed-iy7)."""
    uid = await seed_user(tg_user_id=230)
    ch = Channel(tg_chat_id=9301, username="byid_dormant", title="ByIdDormant")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="dormant", ref_count=0))
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    row = (await db_session.execute(
        text("SELECT kind, channel_username FROM channel_join_queue WHERE id = :id"),
        {"id": body["queue_id"]},
    )).mappings().one()
    assert row["kind"] == "public_username"
    assert row["channel_username"] == "byid_dormant"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_queues_left_channel(
    async_client, db_session, seed_user
) -> None:
    """A legacy `left` subscription is reactivated through the queue too."""
    uid = await seed_user(tg_user_id=231)
    ch = Channel(tg_chat_id=9302, username="byid_left", title="ByIdLeft")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="left", ref_count=0))
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_by_id_queues_dormant_private(
    async_client, db_session, seed_user
) -> None:
    """A dormant private channel (no username, has invite_hash) is queued
    as a private-invite join."""
    uid = await seed_user(tg_user_id=232)
    ch = Channel(
        tg_chat_id=9303, username=None, title="ByIdPrivate",
        invite_hash="privhash123",
    )
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="dormant", ref_count=0))
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}", headers=_auth(uid))
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    row = (await db_session.execute(
        text("SELECT kind, invite_hash FROM channel_join_queue WHERE id = :id"),
        {"id": body["queue_id"]},
    )).mappings().one()
    assert row["kind"] == "private_invite"
    assert row["invite_hash"] == "privhash123"


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
