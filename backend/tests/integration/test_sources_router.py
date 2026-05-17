import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_existing_channel(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=11)
    ch = Channel(tg_chat_id=22222, username="meduzaproject", title="Meduza")
    db_session.add(ch)
    await db_session.commit()

    r = await async_client.post(
        "/sources", json={"username": "meduzaproject"}, headers=_auth(user_id)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "subscribed"
    assert body["channel"]["username"] == "meduzaproject"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_enqueues_unknown(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=12)

    r = await async_client.post(
        "/sources", json={"username": "freshchannel"}, headers=_auth(user_id)
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert isinstance(body["queue_id"], int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_sources_returns_user_list(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=13)
    ch = Channel(tg_chat_id=33333, username="news", title="News")
    db_session.add(ch)
    await db_session.commit()
    await async_client.post("/sources", json={"username": "news"}, headers=_auth(user_id))

    r = await async_client.get("/sources", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["channel"]["username"] == "news"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_status_returns_pending_then_done(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=14)
    r = await async_client.post(
        "/sources", json={"username": "fresh"}, headers=_auth(user_id)
    )
    qid = r.json()["queue_id"]

    r1 = await async_client.get(f"/sources/queue/{qid}", headers=_auth(user_id))
    assert r1.status_code == 200
    assert r1.json()["status"] == "pending"

    # Simulate ingester completing the request.
    from shared.models import ChannelJoinQueue, Channel
    ch = Channel(tg_chat_id=44444, username="fresh", title="Fresh")
    db_session.add(ch)
    await db_session.commit()
    qrow = await db_session.get(ChannelJoinQueue, qid)
    qrow.status = "done"
    qrow.channel_id = ch.id
    await db_session.commit()

    r2 = await async_client.get(f"/sources/queue/{qid}", headers=_auth(user_id))
    assert r2.json()["status"] == "done"
    assert r2.json()["channel"]["username"] == "fresh"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_source_decrements_ref(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=15)
    ch = Channel(tg_chat_id=55555, username="bye", title="Bye")
    db_session.add(ch)
    await db_session.commit()
    await async_client.post("/sources", json={"username": "bye"}, headers=_auth(user_id))

    r = await async_client.delete(f"/sources/{ch.id}", headers=_auth(user_id))
    assert r.status_code == 204

    rows = (await async_client.get("/sources", headers=_auth(user_id))).json()["items"]
    assert rows == []
