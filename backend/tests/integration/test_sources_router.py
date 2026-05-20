import pytest
from sqlalchemy import text

from shared.auth.jwt import encode_access
from shared.models import Channel, ChannelSubscription, UserHiddenChannel


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
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    await db_session.commit()

    r = await async_client.post(
        "/sources", json={"input": "meduzaproject"}, headers=_auth(user_id)
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
        "/sources", json={"input": "freshchannel"}, headers=_auth(user_id)
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert isinstance(body["queue_id"], int)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_sources_returns_user_list(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=13)
    ch = Channel(tg_chat_id=33333, username="newschan", title="News")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    await db_session.commit()
    await async_client.post("/sources", json={"input": "newschan"}, headers=_auth(user_id))

    r = await async_client.get("/sources", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["channel"]["username"] == "newschan"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_status_returns_pending_then_done(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=14)
    r = await async_client.post(
        "/sources", json={"input": "freshzz"}, headers=_auth(user_id)
    )
    qid = r.json()["queue_id"]

    r1 = await async_client.get(f"/sources/queue/{qid}", headers=_auth(user_id))
    assert r1.status_code == 200
    assert r1.json()["status"] == "pending"

    # Simulate ingester completing the request.
    from shared.models import ChannelJoinQueue, Channel
    ch = Channel(tg_chat_id=44444, username="freshzz", title="Fresh")
    db_session.add(ch)
    await db_session.commit()
    qrow = await db_session.get(ChannelJoinQueue, qid)
    qrow.status = "done"
    qrow.channel_id = ch.id
    await db_session.commit()

    r2 = await async_client.get(f"/sources/queue/{qid}", headers=_auth(user_id))
    assert r2.json()["status"] == "done"
    assert r2.json()["channel"]["username"] == "freshzz"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_source_decrements_ref(async_client, db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=15)
    ch = Channel(tg_chat_id=55555, username="byebye", title="Bye")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    await db_session.commit()
    await async_client.post("/sources", json={"input": "byebye"}, headers=_auth(user_id))

    r = await async_client.delete(f"/sources/{ch.id}", headers=_auth(user_id))
    assert r.status_code == 204

    rows = (await async_client.get("/sources", headers=_auth(user_id))).json()["items"]
    assert rows == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_dormant_channel_queues(
    async_client, db_session, seed_user
) -> None:
    """Re-subscribing by username to a known-but-dormant channel goes
    through the join queue so the ingester reactivates it (telegram-feed-iy7)."""
    user_id = await seed_user(tg_user_id=420)
    ch = Channel(tg_chat_id=42001, username="dormantchan", title="Dormant")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(
        ChannelSubscription(channel_id=ch.id, status="dormant", ref_count=0)
    )
    await db_session.commit()

    r = await async_client.post(
        "/sources", json={"input": "dormantchan"}, headers=_auth(user_id)
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    row = (await db_session.execute(
        text(
            "SELECT kind, channel_username, status "
            "FROM channel_join_queue WHERE id = :id"
        ),
        {"id": body["queue_id"]},
    )).mappings().one()
    assert row["kind"] == "public_username"
    assert row["channel_username"] == "dormantchan"
    assert row["status"] == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_dedup_returns_existing_queue_id(
    async_client, db_session, seed_user
) -> None:
    """A second POST while the first join is still pending returns the
    same queue_id — no duplicate channel_join_queue row."""
    user_id = await seed_user(tg_user_id=421)
    ch = Channel(tg_chat_id=42101, username="dedupchan", title="Dedup")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(
        ChannelSubscription(channel_id=ch.id, status="dormant", ref_count=0)
    )
    await db_session.commit()

    r1 = await async_client.post(
        "/sources", json={"input": "dedupchan"}, headers=_auth(user_id)
    )
    r2 = await async_client.post(
        "/sources", json={"input": "dedupchan"}, headers=_auth(user_id)
    )
    assert r1.status_code == 202 and r2.status_code == 202, (r1.text, r2.text)
    assert r1.json()["queue_id"] == r2.json()["queue_id"]
    count = (await db_session.execute(
        text("SELECT count(*) FROM channel_join_queue WHERE channel_username = :u"),
        {"u": "dedupchan"},
    )).scalar_one()
    assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_dedup_is_per_user(
    async_client, db_session, seed_user
) -> None:
    """Dedup is scoped per user: a different user re-subscribing to the
    same dormant channel gets their own queue row, so their join (and
    user_source link) is not dropped."""
    uid_a = await seed_user(tg_user_id=422)
    uid_b = await seed_user(tg_user_id=423)
    ch = Channel(tg_chat_id=42201, username="multichan", title="Multi")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(
        ChannelSubscription(channel_id=ch.id, status="dormant", ref_count=0)
    )
    await db_session.commit()

    r_a = await async_client.post(
        "/sources", json={"input": "multichan"}, headers=_auth(uid_a)
    )
    r_b = await async_client.post(
        "/sources", json={"input": "multichan"}, headers=_auth(uid_b)
    )
    assert r_a.status_code == 202 and r_b.status_code == 202, (r_a.text, r_b.text)
    assert r_a.json()["queue_id"] != r_b.json()["queue_id"]
    count = (await db_session.execute(
        text("SELECT count(*) FROM channel_join_queue WHERE channel_username = :u"),
        {"u": "multichan"},
    )).scalar_one()
    assert count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hide_source_persists(async_client, db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=16)
    ch = Channel(tg_chat_id=66666, username="hideme", title="Hideme")
    db_session.add(ch)
    await db_session.commit()

    r = await async_client.post(f"/sources/{ch.id}/hide", headers=_auth(uid))
    assert r.status_code == 204
    assert await db_session.get(UserHiddenChannel, (uid, ch.id)) is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hide_unknown_source_returns_404(async_client, seed_user) -> None:
    uid = await seed_user(tg_user_id=17)
    r = await async_client.post("/sources/999999999/hide", headers=_auth(uid))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "channel_not_found"


# -----------------------------------------------------------------------------
# T4: private invite dispatch + parser-based input handling
# -----------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_private_invite_queued(async_client, db_session, seed_user):
    user_id = await seed_user(tg_user_id=2025001)
    headers = _auth(user_id)
    resp = await async_client.post(
        "/sources", json={"input": "https://t.me/+abcDEF_123"}, headers=headers
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["channel"] is None
    queue_id = body["queue_id"]
    row = (await db_session.execute(
        text("SELECT kind, invite_hash, channel_username, status FROM channel_join_queue WHERE id = :id"),
        {"id": queue_id},
    )).mappings().one()
    assert row["kind"] == "private_invite"
    assert row["invite_hash"] == "abcDEF_123"
    assert row["channel_username"] is None
    assert row["status"] == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_legacy_joinchat_queued(async_client, db_session, seed_user):
    user_id = await seed_user(tg_user_id=2025002)
    headers = _auth(user_id)
    resp = await async_client.post(
        "/sources", json={"input": "https://t.me/joinchat/abc-DEF_123"}, headers=headers
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "queued"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_invalid_input(async_client, db_session, seed_user):
    user_id = await seed_user(tg_user_id=2025003)
    headers = _auth(user_id)
    resp = await async_client.post("/sources", json={"input": "!!! garbage !!!"}, headers=headers)
    assert resp.status_code == 400
    body = resp.json()
    # API uses APIError which surfaces as body["error"]["code"]
    assert (
        body.get("error", {}).get("code") == "invalid_source_input"
        or body.get("detail", {}).get("code") == "invalid_source_input"
        or body.get("detail") == "invalid_source_input"
        or "invalid_source_input" in str(body)
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_sources_public_username_via_url(async_client, db_session, seed_user):
    """Regression: t.me/<username> URL also accepted as public."""
    user_id = await seed_user(tg_user_id=2025004)
    headers = _auth(user_id)
    resp = await async_client.post(
        "/sources", json={"input": "https://t.me/somechannel"}, headers=headers
    )
    assert resp.status_code in (200, 202)
    if resp.status_code == 202:
        body = resp.json()
        queue_id = body["queue_id"]
        row = (await db_session.execute(
            text("SELECT kind, channel_username FROM channel_join_queue WHERE id = :id"),
            {"id": queue_id},
        )).mappings().one()
        assert row["kind"] == "public_username"
        assert row["channel_username"] == "somechannel"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_status_pending_approval(async_client, db_session, seed_user):
    user_id = await seed_user(tg_user_id=2025005)
    queue_id = (await db_session.execute(
        text("""
            INSERT INTO channel_join_queue (kind, invite_hash, requested_by_user_id, status)
            VALUES ('private_invite', 'abc12345', :uid, 'pending_approval')
            RETURNING id
        """),
        {"uid": user_id},
    )).scalar_one()
    await db_session.commit()
    resp = await async_client.get(f"/sources/queue/{queue_id}", headers=_auth(user_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_approval"
    assert body["error_code"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_queue_status_failed_with_error_code(async_client, db_session, seed_user):
    user_id = await seed_user(tg_user_id=2025006)
    queue_id = (await db_session.execute(
        text("""
            INSERT INTO channel_join_queue (kind, invite_hash, requested_by_user_id, status, error_code)
            VALUES ('private_invite', 'def67890', :uid, 'failed', 'invite_expired')
            RETURNING id
        """),
        {"uid": user_id},
    )).scalar_one()
    await db_session.commit()
    resp = await async_client.get(f"/sources/queue/{queue_id}", headers=_auth(user_id))
    assert resp.status_code == 200
    assert resp.json()["error_code"] == "invite_expired"
