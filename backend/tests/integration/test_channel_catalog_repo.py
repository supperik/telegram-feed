from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete

from api.pagination import CatalogCursor
from shared.models import (
    Channel,
    ChannelSubscription,
    UserCatalogHiddenChannel,
    UserSource,
)
from shared.repositories.channel_catalog import list_catalog_available


@pytest_asyncio.fixture(autouse=True)
async def _reset_catalog_dependent_rows(db_session):
    """Catalog listing joins Channel with ChannelSubscription; rows from
    earlier tests in the shared session (admin_*, etc.) that have active
    subscriptions would otherwise contaminate the global result.

    Wiping the catalog-input tables (subscriptions, user_sources, hidden)
    is FK-safe: nothing else in the schema references them. Channels and
    posts are left untouched so adjacent tests keep their data."""
    await db_session.execute(delete(UserCatalogHiddenChannel))
    await db_session.execute(delete(UserSource))
    await db_session.execute(delete(ChannelSubscription))
    await db_session.commit()
    yield


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_available_excludes_banned_inactive_orphaned_and_hidden(
    db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=101)

    # active subscribed by someone — should appear
    ch_active = Channel(tg_chat_id=1001, username="cat_a", title="A", posts_count=10)
    # banned — must NOT appear
    ch_banned = Channel(
        tg_chat_id=1002, username="cat_b", title="B", banned=True, posts_count=5
    )
    # inactive subscription — must NOT appear
    ch_inactive = Channel(tg_chat_id=1003, username="cat_c", title="C", posts_count=3)
    # ref_count == 0 orphan — must NOT appear
    ch_orphan = Channel(tg_chat_id=1004, username="cat_d", title="D", posts_count=2)
    # active but hidden by this user — must NOT appear
    ch_hidden = Channel(tg_chat_id=1005, username="cat_e", title="E", posts_count=20)
    db_session.add_all([ch_active, ch_banned, ch_inactive, ch_orphan, ch_hidden])
    await db_session.commit()

    db_session.add_all([
        ChannelSubscription(channel_id=ch_active.id, status="active", ref_count=2),
        ChannelSubscription(channel_id=ch_banned.id, status="active", ref_count=1),
        ChannelSubscription(channel_id=ch_inactive.id, status="failed", ref_count=1),
        ChannelSubscription(channel_id=ch_orphan.id, status="active", ref_count=0),
        ChannelSubscription(channel_id=ch_hidden.id, status="active", ref_count=1),
        UserCatalogHiddenChannel(user_id=uid, channel_id=ch_hidden.id),
    ])
    await db_session.commit()

    rows = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_available(),
        limit=50,
        q=None,
    )
    assert [r.channel_id for r in rows] == [ch_active.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_available_sorts_by_posts_count_then_id(
    db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=102)
    c1 = Channel(tg_chat_id=2001, username="cat_c1", title="C1", posts_count=5)
    c2 = Channel(tg_chat_id=2002, username="cat_c2", title="C2", posts_count=10)
    c3 = Channel(tg_chat_id=2003, username="cat_c3", title="C3", posts_count=10)
    db_session.add_all([c1, c2, c3])
    await db_session.commit()
    for c in (c1, c2, c3):
        db_session.add(ChannelSubscription(channel_id=c.id, status="active", ref_count=1))
    await db_session.commit()

    rows = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_available(),
        limit=50,
        q=None,
    )
    # 10 then 10 (id DESC) then 5 — so c3 (id desc among ties), c2, c1
    ids = [r.channel_id for r in rows]
    assert ids == [c3.id, c2.id, c1.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_available_keyset_pagination(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=103)
    channels = []
    for i in range(5):
        c = Channel(
            tg_chat_id=3000 + i, username=f"cat_k{i}", title=f"K{i}",
            posts_count=10 - i,  # 10, 9, 8, 7, 6
        )
        channels.append(c)
        db_session.add(c)
    await db_session.commit()
    for c in channels:
        db_session.add(ChannelSubscription(channel_id=c.id, status="active", ref_count=1))
    await db_session.commit()

    page1 = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_available(),
        limit=2,
        q=None,
    )
    assert len(page1) == 2
    last = page1[-1]
    page2 = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.available(
            posts_count=last.posts_count, channel_id=last.channel_id
        ),
        limit=2,
        q=None,
    )
    assert len(page2) == 2
    # No overlap between pages
    assert {r.channel_id for r in page1}.isdisjoint({r.channel_id for r in page2})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_available_q_filter_case_insensitive(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=104)
    ch1 = Channel(tg_chat_id=4001, username="cat_meduza", title="Meduza Project", posts_count=1)
    ch2 = Channel(tg_chat_id=4002, username="cat_other", title="Other", posts_count=1)
    db_session.add_all([ch1, ch2])
    await db_session.commit()
    for c in (ch1, ch2):
        db_session.add(ChannelSubscription(channel_id=c.id, status="active", ref_count=1))
    await db_session.commit()

    rows = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_available(),
        limit=50,
        q="medU",
    )
    assert [r.channel_id for r in rows] == [ch1.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_available_marks_is_subscribed(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=105)
    ch = Channel(tg_chat_id=5001, username="cat_sub", title="Sub", posts_count=1)
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    db_session.add(UserSource(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    rows = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_available(),
        limit=50,
        q=None,
    )
    assert len(rows) == 1
    assert rows[0].is_subscribed is True
