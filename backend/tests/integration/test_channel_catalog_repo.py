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
from shared.repositories.channel_catalog import (
    hide_from_catalog,
    list_catalog_available,
    list_catalog_hidden,
    unhide_from_catalog,
)


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_available_q_filter_treats_wildcards_as_literals(
    db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=120)
    # Note: username `cat_other` is already used by the case-insensitive test
    # earlier in the file; the autouse cleanup fixture wipes subscriptions but
    # leaves Channel rows behind. Use a unique username here.
    ch_pct = Channel(
        tg_chat_id=8001, username="cat_pct", title="100% real", posts_count=1,
    )
    ch_other = Channel(
        tg_chat_id=8002, username="cat_pct_other", title="other channel", posts_count=1,
    )
    db_session.add_all([ch_pct, ch_other])
    await db_session.commit()
    for c in (ch_pct, ch_other):
        db_session.add(ChannelSubscription(channel_id=c.id, status="active", ref_count=1))
    await db_session.commit()

    # `%` must be treated as a literal — only the row with literal % should match.
    rows = await list_catalog_available(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_available(),
        limit=50,
        q="100%",
    )
    assert [r.channel_id for r in rows] == [ch_pct.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hide_unhide_round_trip_idempotent(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=110)
    ch = Channel(tg_chat_id=6001, username="cat_z", title="Z", posts_count=1)
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=1))
    await db_session.commit()

    await hide_from_catalog(db_session, user_id=uid, channel_id=ch.id)
    await hide_from_catalog(db_session, user_id=uid, channel_id=ch.id)  # idempotent
    await db_session.commit()
    assert (
        await db_session.get(UserCatalogHiddenChannel, (uid, ch.id))
    ) is not None

    await unhide_from_catalog(db_session, user_id=uid, channel_id=ch.id)
    await unhide_from_catalog(db_session, user_id=uid, channel_id=ch.id)  # idempotent
    await db_session.commit()
    assert (
        await db_session.get(UserCatalogHiddenChannel, (uid, ch.id))
    ) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_hidden_returns_only_user_hidden_sorted_by_hidden_at_desc(
    db_session, seed_user
) -> None:
    uid = await seed_user(tg_user_id=111)
    other = await seed_user(tg_user_id=112)
    c_a = Channel(tg_chat_id=7001, username="cat_ha", title="HA", posts_count=1)
    c_b = Channel(tg_chat_id=7002, username="cat_hb", title="HB", posts_count=1)
    c_c = Channel(tg_chat_id=7003, username="cat_hc", title="HC", posts_count=1)
    c_banned = Channel(
        tg_chat_id=7004, username="cat_hban", title="HBan", posts_count=1, banned=True,
    )
    db_session.add_all([c_a, c_b, c_c, c_banned])
    await db_session.commit()
    for c in (c_a, c_b, c_c, c_banned):
        db_session.add(ChannelSubscription(channel_id=c.id, status="active", ref_count=1))
    await db_session.commit()

    # uid hid a, then c, then banned. b is hidden by `other`.
    await hide_from_catalog(db_session, user_id=uid, channel_id=c_a.id)
    await db_session.commit()
    await hide_from_catalog(db_session, user_id=uid, channel_id=c_c.id)
    await db_session.commit()
    await hide_from_catalog(db_session, user_id=uid, channel_id=c_banned.id)
    await db_session.commit()
    await hide_from_catalog(db_session, user_id=other, channel_id=c_b.id)
    await db_session.commit()

    rows = await list_catalog_hidden(
        db_session,
        user_id=uid,
        cursor=CatalogCursor.initial_hidden(),
        limit=50,
    )
    # banned excluded, only uid's hidden, newest first
    assert [r.channel_id for r in rows] == [c_c.id, c_a.id]
    assert all(r.is_hidden_from_catalog for r in rows)
