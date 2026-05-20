"""Integration tests for shared.repositories.channel_backfill."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.models import (
    Channel,
    ChannelBackfillState,
    ChannelSubscription,
    Post,
    User,
    UserReadPost,
    UserSource,
)
from shared.repositories.channel_backfill import (
    defer_after_flood_wait,
    mark_fully_backfilled,
    release_lock,
    select_eligible_channels,
    try_acquire_lock,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_POSTED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def _mk_channel(session, *, tg_chat_id, banned=False, sub_status="active"):
    ch = Channel(
        tg_chat_id=tg_chat_id, title=f"ch-{tg_chat_id}",
        username=f"ch_{tg_chat_id}", banned=banned,
    )
    session.add(ch)
    await session.flush()
    session.add(ChannelSubscription(
        channel_id=ch.id, status=sub_status, ref_count=1))
    await session.flush()
    return ch.id


async def _mk_user(session, *, tg_user_id):
    u = User(tg_user_id=tg_user_id, tg_first_name="U", tg_username=f"u{tg_user_id}")
    session.add(u)
    await session.flush()
    return u.id


async def _mk_posts(session, *, channel_id, msg_ids):
    post_ids = []
    for mid in msg_ids:
        p = Post(channel_id=channel_id, tg_message_id=mid, posted_at=_POSTED_AT)
        session.add(p)
        await session.flush()
        post_ids.append(p.id)
    return post_ids


async def _follow(session, *, user_id, channel_id):
    session.add(UserSource(user_id=user_id, channel_id=channel_id))
    await session.flush()


async def _mark_read(session, *, user_id, post_ids):
    for pid in post_ids:
        session.add(UserReadPost(user_id=user_id, post_id=pid))
    await session.flush()


async def _reload(session, cid):
    session.expire_all()
    return await session.get(ChannelBackfillState, cid)


async def test_try_acquire_lock_acquires_blocks_and_expires(db_session):
    cid = await _mk_channel(db_session, tg_chat_id=8001001)
    await db_session.commit()

    assert await try_acquire_lock(db_session, channel_id=cid, ttl_seconds=300) is True
    await db_session.commit()

    # Locked -> second call denied.
    assert await try_acquire_lock(db_session, channel_id=cid, ttl_seconds=300) is False
    await db_session.commit()

    # Force the lock into the past -> re-acquirable.
    st = await _reload(db_session, cid)
    st.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert await try_acquire_lock(db_session, channel_id=cid, ttl_seconds=300) is True
    await db_session.commit()


async def test_lock_state_transitions(db_session):
    cid = await _mk_channel(db_session, tg_chat_id=8001002)
    await db_session.commit()
    await try_acquire_lock(db_session, channel_id=cid, ttl_seconds=300)
    await db_session.commit()

    await release_lock(db_session, channel_id=cid, oldest_seen_msg_id=77)
    await db_session.commit()
    st = await _reload(db_session, cid)
    assert st.locked_until is None
    assert st.oldest_seen_msg_id == 77
    assert st.last_backfill_at is not None
    assert st.fully_backfilled is False

    await defer_after_flood_wait(db_session, channel_id=cid, seconds=600)
    await db_session.commit()
    st = await _reload(db_session, cid)
    assert st.locked_until is not None
    assert st.locked_until > datetime.now(timezone.utc)

    await mark_fully_backfilled(db_session, channel_id=cid)
    await db_session.commit()
    st = await _reload(db_session, cid)
    assert st.fully_backfilled is True
    assert st.locked_until is None


async def test_select_eligible_channels_filters_and_orders(db_session):
    """Seed a spread of channels; only the two with a follower whose unread
    count is <= K (=2) and that pass every channel-level gate are returned."""
    uid = await _mk_user(db_session, tg_user_id=8002001)

    # Eligible: 5 posts, follower read 4 -> unread 1.
    elig = await _mk_channel(db_session, tg_chat_id=8003001)
    pe = await _mk_posts(db_session, channel_id=elig, msg_ids=[100, 101, 102, 103, 104])
    await _follow(db_session, user_id=uid, channel_id=elig)
    await _mark_read(db_session, user_id=uid, post_ids=pe[:4])

    # Eligible: 3 posts, follower read all -> unread 0. Has a stored cursor.
    zero = await _mk_channel(db_session, tg_chat_id=8003002)
    pz = await _mk_posts(db_session, channel_id=zero, msg_ids=[200, 201, 202])
    await _follow(db_session, user_id=uid, channel_id=zero)
    await _mark_read(db_session, user_id=uid, post_ids=pz)
    db_session.add(ChannelBackfillState(
        channel_id=zero, oldest_seen_msg_id=55,
        last_backfill_at=datetime(2026, 5, 1, tzinfo=timezone.utc)))

    # Excluded: well-read channel - 10 posts, follower read 3 -> unread 7 > 2.
    well = await _mk_channel(db_session, tg_chat_id=8003003)
    pw = await _mk_posts(db_session, channel_id=well, msg_ids=list(range(300, 310)))
    await _follow(db_session, user_id=uid, channel_id=well)
    await _mark_read(db_session, user_id=uid, post_ids=pw[:3])

    # Excluded: banned.
    banned = await _mk_channel(db_session, tg_chat_id=8003004, banned=True)
    pb = await _mk_posts(db_session, channel_id=banned, msg_ids=[400, 401])
    await _follow(db_session, user_id=uid, channel_id=banned)
    await _mark_read(db_session, user_id=uid, post_ids=pb)

    # Excluded: no follower.
    nofol = await _mk_channel(db_session, tg_chat_id=8003005)
    await _mk_posts(db_session, channel_id=nofol, msg_ids=[500, 501])

    # Excluded: already fully backfilled.
    full = await _mk_channel(db_session, tg_chat_id=8003006)
    pf = await _mk_posts(db_session, channel_id=full, msg_ids=[600, 601])
    await _follow(db_session, user_id=uid, channel_id=full)
    await _mark_read(db_session, user_id=uid, post_ids=pf)
    db_session.add(ChannelBackfillState(channel_id=full, fully_backfilled=True))

    # Excluded: locked.
    locked = await _mk_channel(db_session, tg_chat_id=8003007)
    pl = await _mk_posts(db_session, channel_id=locked, msg_ids=[700, 701])
    await _follow(db_session, user_id=uid, channel_id=locked)
    await _mark_read(db_session, user_id=uid, post_ids=pl)
    db_session.add(ChannelBackfillState(
        channel_id=locked,
        locked_until=datetime.now(timezone.utc) + timedelta(hours=1)))

    # Excluded: subscription not active.
    inact = await _mk_channel(db_session, tg_chat_id=8003008, sub_status="left")
    pi = await _mk_posts(db_session, channel_id=inact, msg_ids=[800, 801])
    await _follow(db_session, user_id=uid, channel_id=inact)
    await _mark_read(db_session, user_id=uid, post_ids=pi)

    await db_session.commit()

    rows = await select_eligible_channels(db_session, unread_threshold=2, limit=50)
    by_id = {cid: (chat, cursor) for cid, chat, cursor in rows}

    assert set(by_id) == {elig, zero}
    # Cursor: no stored value -> min(tg_message_id); stored value wins.
    assert by_id[elig][1] == 100
    assert by_id[zero][1] == 55
    # Round-robin: last_backfill_at NULLS FIRST -> elig (NULL) before zero.
    assert [cid for cid, _, _ in rows] == [elig, zero]
