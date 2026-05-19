from datetime import UTC, datetime, timedelta

import pytest

from shared.models import (
    Channel,
    Media,
    Post,
    UserHiddenPost,
    UserSavedPost,
    UserSource,
)
from shared.repositories.feed import (
    fetch_hidden_posts_page,
    fetch_saved_posts_page,
)


async def _make_post(db_session, channel, *, tg_message_id, posted_at, text=None):
    p = Post(
        channel_id=channel.id,
        tg_message_id=tg_message_id,
        text=text,
        posted_at=posted_at,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.mark.integration
@pytest.mark.asyncio
async def test_saved_keyset_orders_by_saved_at_desc_and_paginates(
    db_session, seed_user
) -> None:
    user_id = await seed_user(tg_user_id=601)
    ch = Channel(tg_chat_id=80001, username="s_chan", title="S")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    await db_session.commit()

    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    posts = []
    for i in range(5):
        posts.append(
            await _make_post(
                db_session, ch,
                tg_message_id=300 + i, text=f"s{i}", posted_at=base + timedelta(minutes=i),
            )
        )

    # Save in reverse order so saved_at order differs from posted_at order:
    # we save post 4 first, then 3, ..., then 0. Expect newest saved on top.
    save_base = datetime(2026, 2, 1, tzinfo=UTC)
    for offset, p in enumerate(reversed(posts)):
        db_session.add(
            UserSavedPost(
                user_id=user_id,
                post_id=p.id,
                saved_at=save_base + timedelta(minutes=offset),
            )
        )
        await db_session.commit()

    page1 = await fetch_saved_posts_page(
        db_session,
        user_id=user_id,
        cursor_saved_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=3,
    )
    # First saved was posts[4] (offset 0) → saved earliest → last in DESC order.
    # Last saved was posts[0] (offset 4) → saved latest → first in DESC order.
    assert [r.tg_message_id for r in page1] == [300, 301, 302]
    assert all(r.is_saved is True for r in page1)
    assert all(r.sort_at is not None for r in page1)

    last = page1[-1]
    page2 = await fetch_saved_posts_page(
        db_session,
        user_id=user_id,
        cursor_saved_at=last.sort_at,
        cursor_post_id=last.post_id,
        limit=3,
    )
    assert [r.tg_message_id for r in page2] == [303, 304]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_saved_isolated_by_user(db_session, seed_user) -> None:
    uid_a = await seed_user(tg_user_id=602)
    uid_b = await seed_user(tg_user_id=603)
    ch = Channel(tg_chat_id=80002, username="iso_s", title="iso")
    db_session.add(ch)
    await db_session.commit()
    p = await _make_post(
        db_session, ch, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    db_session.add(UserSavedPost(user_id=uid_a, post_id=p.id))
    await db_session.commit()

    page_a = await fetch_saved_posts_page(
        db_session,
        user_id=uid_a,
        cursor_saved_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=10,
    )
    page_b = await fetch_saved_posts_page(
        db_session,
        user_id=uid_b,
        cursor_saved_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=10,
    )
    assert [r.post_id for r in page_a] == [p.id]
    assert page_b == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_saved_excludes_banned_channels(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=604)
    ch_ok = Channel(tg_chat_id=80010, username="ok_s", title="ok")
    ch_bad = Channel(tg_chat_id=80011, username="bad_s", title="bad", banned=True)
    db_session.add_all([ch_ok, ch_bad])
    await db_session.commit()
    p_ok = await _make_post(
        db_session, ch_ok, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    p_bad = await _make_post(
        db_session, ch_bad, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    db_session.add_all(
        [
            UserSavedPost(user_id=uid, post_id=p_ok.id),
            UserSavedPost(user_id=uid, post_id=p_bad.id),
        ]
    )
    await db_session.commit()

    rows = await fetch_saved_posts_page(
        db_session,
        user_id=uid,
        cursor_saved_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=10,
    )
    assert [r.post_id for r in rows] == [p_ok.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_saved_includes_media(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=605)
    ch = Channel(tg_chat_id=80020, username="m_s", title="m")
    db_session.add(ch)
    await db_session.commit()
    p = await _make_post(
        db_session, ch, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    db_session.add_all(
        [
            Media(post_id=p.id, type="photo", tg_file_id="ph1", position=0, width=100, height=80),
            Media(post_id=p.id, type="photo", tg_file_id="ph2", position=1, width=200, height=160),
        ]
    )
    db_session.add(UserSavedPost(user_id=uid, post_id=p.id))
    await db_session.commit()

    rows = await fetch_saved_posts_page(
        db_session,
        user_id=uid,
        cursor_saved_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=10,
    )
    assert len(rows) == 1
    assert [m.type for m in rows[0].media] == ["photo", "photo"]
    assert [m.width for m in rows[0].media] == [100, 200]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hidden_keyset_orders_by_hidden_at_desc_and_paginates(
    db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=701)
    ch = Channel(tg_chat_id=81001, username="h_chan", title="H")
    db_session.add(ch)
    await db_session.commit()
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    posts = []
    for i in range(5):
        posts.append(
            await _make_post(
                db_session, ch,
                tg_message_id=400 + i, text=f"h{i}", posted_at=base + timedelta(minutes=i),
            )
        )

    hidden_base = datetime(2026, 3, 1, tzinfo=UTC)
    for offset, p in enumerate(reversed(posts)):
        db_session.add(
            UserHiddenPost(
                user_id=uid,
                post_id=p.id,
                hidden_at=hidden_base + timedelta(minutes=offset),
            )
        )
        await db_session.commit()

    page1 = await fetch_hidden_posts_page(
        db_session,
        user_id=uid,
        cursor_hidden_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=3,
    )
    assert [r.tg_message_id for r in page1] == [400, 401, 402]
    assert all(r.sort_at is not None for r in page1)

    last = page1[-1]
    page2 = await fetch_hidden_posts_page(
        db_session,
        user_id=uid,
        cursor_hidden_at=last.sort_at,
        cursor_post_id=last.post_id,
        limit=3,
    )
    assert [r.tg_message_id for r in page2] == [403, 404]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hidden_reflects_is_saved_flag(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=702)
    ch = Channel(tg_chat_id=81002, username="hs", title="HS")
    db_session.add(ch)
    await db_session.commit()
    p_just_hidden = await _make_post(
        db_session, ch, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    p_hidden_and_saved = await _make_post(
        db_session, ch, tg_message_id=2, posted_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    db_session.add_all(
        [
            UserHiddenPost(user_id=uid, post_id=p_just_hidden.id),
            UserHiddenPost(user_id=uid, post_id=p_hidden_and_saved.id),
            UserSavedPost(user_id=uid, post_id=p_hidden_and_saved.id),
        ]
    )
    await db_session.commit()

    rows = await fetch_hidden_posts_page(
        db_session,
        user_id=uid,
        cursor_hidden_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=10,
    )
    by_id = {r.post_id: r for r in rows}
    assert by_id[p_just_hidden.id].is_saved is False
    assert by_id[p_hidden_and_saved.id].is_saved is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hidden_excludes_banned_channels(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=703)
    ch_ok = Channel(tg_chat_id=81010, username="ok_h", title="ok")
    ch_bad = Channel(tg_chat_id=81011, username="bad_h", title="bad", banned=True)
    db_session.add_all([ch_ok, ch_bad])
    await db_session.commit()
    p_ok = await _make_post(
        db_session, ch_ok, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    p_bad = await _make_post(
        db_session, ch_bad, tg_message_id=1, posted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    db_session.add_all(
        [
            UserHiddenPost(user_id=uid, post_id=p_ok.id),
            UserHiddenPost(user_id=uid, post_id=p_bad.id),
        ]
    )
    await db_session.commit()

    rows = await fetch_hidden_posts_page(
        db_session,
        user_id=uid,
        cursor_hidden_at=datetime(9999, 12, 31, tzinfo=UTC),
        cursor_post_id=0,
        limit=10,
    )
    assert [r.post_id for r in rows] == [p_ok.id]
