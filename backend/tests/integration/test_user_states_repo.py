from datetime import datetime, timezone

import pytest

from shared.models import Channel, Post, UserHiddenChannel, UserHiddenPost, UserSavedPost, UserSource
from shared.repositories.user_states import (
    hide_channel,
    hide_post,
    list_hidden_channels,
    save_post,
    unhide_channel,
    unsave_post,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_unsave_roundtrip(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=41)
    ch = Channel(tg_chat_id=90001, username="x", title="X")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()

    await save_post(db_session, user_id=uid, post_id=p.id)
    await save_post(db_session, user_id=uid, post_id=p.id)  # idempotent
    await db_session.commit()
    assert await db_session.get(UserSavedPost, (uid, p.id)) is not None

    await unsave_post(db_session, user_id=uid, post_id=p.id)
    await db_session.commit()
    assert await db_session.get(UserSavedPost, (uid, p.id)) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hide_post_and_channel_are_idempotent(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=43)
    ch = Channel(tg_chat_id=90002, username="y", title="Y")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()

    await hide_post(db_session, user_id=uid, post_id=p.id)
    await hide_post(db_session, user_id=uid, post_id=p.id)
    await db_session.commit()
    assert await db_session.get(UserHiddenPost, (uid, p.id)) is not None

    await hide_channel(db_session, user_id=uid, channel_id=ch.id)
    await hide_channel(db_session, user_id=uid, channel_id=ch.id)
    await db_session.commit()
    assert await db_session.get(UserHiddenChannel, (uid, ch.id)) is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unhide_channel_is_idempotent(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=5101)
    ch = Channel(tg_chat_id=91101, username="uh", title="UH")
    db_session.add(ch)
    await db_session.commit()

    await hide_channel(db_session, user_id=uid, channel_id=ch.id)
    await db_session.commit()
    assert await db_session.get(UserHiddenChannel, (uid, ch.id)) is not None

    await unhide_channel(db_session, user_id=uid, channel_id=ch.id)
    await db_session.commit()
    assert await db_session.get(UserHiddenChannel, (uid, ch.id)) is None

    await unhide_channel(db_session, user_id=uid, channel_id=ch.id)
    await db_session.commit()
    assert await db_session.get(UserHiddenChannel, (uid, ch.id)) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_hidden_channels_returns_subscribed_hidden_sorted(
    db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=5102)
    ch_a = Channel(tg_chat_id=91201, username="lh_a", title="A")
    ch_b = Channel(tg_chat_id=91202, username="lh_b", title="B")
    ch_other = Channel(tg_chat_id=91203, username="lh_o", title="O")  # hidden but not subscribed
    db_session.add_all([ch_a, ch_b, ch_other])
    await db_session.commit()

    db_session.add_all([
        UserSource(user_id=uid, channel_id=ch_a.id),
        UserSource(user_id=uid, channel_id=ch_b.id),
    ])
    await db_session.commit()

    await hide_channel(db_session, user_id=uid, channel_id=ch_a.id)
    await db_session.commit()
    await hide_channel(db_session, user_id=uid, channel_id=ch_b.id)
    await db_session.commit()
    await hide_channel(db_session, user_id=uid, channel_id=ch_other.id)
    await db_session.commit()

    rows = await list_hidden_channels(db_session, user_id=uid)
    assert [r.channel_id for r in rows] == [ch_b.id, ch_a.id]
    assert rows[0].channel_username == "lh_b"
    assert rows[0].channel_title == "B"
    assert rows[0].hidden_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_hidden_channels_isolates_by_user(db_session, seed_user) -> None:
    uid_one = await seed_user(tg_user_id=5103)
    uid_two = await seed_user(tg_user_id=5104)
    ch = Channel(tg_chat_id=91301, username="iso", title="ISO")
    db_session.add(ch)
    await db_session.commit()
    db_session.add_all([
        UserSource(user_id=uid_one, channel_id=ch.id),
        UserSource(user_id=uid_two, channel_id=ch.id),
    ])
    await db_session.commit()

    await hide_channel(db_session, user_id=uid_one, channel_id=ch.id)
    await db_session.commit()

    rows_one = await list_hidden_channels(db_session, user_id=uid_one)
    rows_two = await list_hidden_channels(db_session, user_id=uid_two)
    assert [r.channel_id for r in rows_one] == [ch.id]
    assert rows_two == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_hidden_channels_excludes_banned(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=5105)
    ch_ok = Channel(tg_chat_id=91401, username="ok", title="OK")
    ch_banned = Channel(tg_chat_id=91402, username="bad", title="BAD", banned=True)
    db_session.add_all([ch_ok, ch_banned])
    await db_session.commit()
    db_session.add_all([
        UserSource(user_id=uid, channel_id=ch_ok.id),
        UserSource(user_id=uid, channel_id=ch_banned.id),
    ])
    await db_session.commit()
    await hide_channel(db_session, user_id=uid, channel_id=ch_ok.id)
    await hide_channel(db_session, user_id=uid, channel_id=ch_banned.id)
    await db_session.commit()

    rows = await list_hidden_channels(db_session, user_id=uid)
    assert [r.channel_id for r in rows] == [ch_ok.id]
