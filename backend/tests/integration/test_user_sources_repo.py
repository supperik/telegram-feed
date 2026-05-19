import pytest

from shared.models import Channel, ChannelSubscription
from shared.repositories.user_sources import (
    add_user_source,
    list_user_sources,
    remove_user_source,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_then_remove_user_source(db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=1)
    ch = Channel(tg_chat_id=10001, username="us_repo_meduza", title="Meduza")
    db_session.add(ch)
    await db_session.commit()

    was_new, status = await add_user_source(db_session, user_id=user_id, channel_id=ch.id)
    await db_session.commit()
    assert was_new is True
    assert status in {"pending_backfill", "active"}

    sub = await db_session.get(ChannelSubscription, ch.id)
    assert sub is not None and sub.ref_count == 1

    # Second add is a no-op.
    was_new2, _ = await add_user_source(db_session, user_id=user_id, channel_id=ch.id)
    await db_session.commit()
    assert was_new2 is False
    assert (await db_session.get(ChannelSubscription, ch.id)).ref_count == 1

    rows = await list_user_sources(db_session, user_id=user_id)
    assert len(rows) == 1 and rows[0].channel_username == "us_repo_meduza"

    removed = await remove_user_source(db_session, user_id=user_id, channel_id=ch.id)
    await db_session.commit()
    assert removed is True
    assert (await db_session.get(ChannelSubscription, ch.id)).ref_count == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_remove_when_absent_is_noop(db_session, seed_user) -> None:
    user_id = await seed_user(tg_user_id=2)
    ch = Channel(tg_chat_id=10002, username="us_repo_other", title="Other")
    db_session.add(ch)
    await db_session.commit()

    removed = await remove_user_source(db_session, user_id=user_id, channel_id=ch.id)
    await db_session.commit()
    assert removed is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_add_user_source_clears_catalog_hidden(db_session, seed_user) -> None:
    from shared.models import Channel, ChannelSubscription, UserCatalogHiddenChannel
    from shared.repositories.user_sources import add_user_source

    uid = await seed_user(tg_user_id=130)
    ch = Channel(tg_chat_id=8101, username="cat_cs", title="CS", posts_count=1)
    db_session.add(ch)
    await db_session.commit()
    db_session.add(ChannelSubscription(channel_id=ch.id, status="active", ref_count=0))
    db_session.add(UserCatalogHiddenChannel(user_id=uid, channel_id=ch.id))
    await db_session.commit()
    assert (
        await db_session.get(UserCatalogHiddenChannel, (uid, ch.id))
    ) is not None

    await add_user_source(db_session, user_id=uid, channel_id=ch.id)
    await db_session.commit()

    assert (
        await db_session.get(UserCatalogHiddenChannel, (uid, ch.id))
    ) is None
