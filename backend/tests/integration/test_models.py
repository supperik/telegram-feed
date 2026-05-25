import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import select


@pytest.mark.integration
def test_models_round_trip(configured_env, pg_container):
    async def run():
        from shared.db import make_engine, make_session_factory
        from shared.models import Channel, Post, User, UserSource

        engine = make_engine(pg_container["async_url"])
        factory = make_session_factory(engine)
        async with factory() as s:
            user = User(tg_user_id=42, tg_username="alice")
            channel = Channel(tg_chat_id=-100123, username="testchan", title="Test")
            s.add_all([user, channel])
            await s.flush()
            src = UserSource(user_id=user.id, channel_id=channel.id)
            post = Post(
                channel_id=channel.id,
                tg_message_id=1,
                text="hello",
                posted_at=datetime.now(tz=timezone.utc),
            )
            s.add_all([src, post])
            await s.commit()

            res = await s.execute(select(Post).where(Post.channel_id == channel.id))
            row = res.scalar_one()
            assert row.text == "hello"
        await engine.dispose()

    asyncio.run(run())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_catalog_hidden_channel_insert(db_session, seed_user) -> None:
    from shared.models import Channel, UserCatalogHiddenChannel

    uid = await seed_user(tg_user_id=901)
    ch = Channel(tg_chat_id=900001, username="x_cat", title="X")
    db_session.add(ch)
    await db_session.commit()

    db_session.add(UserCatalogHiddenChannel(user_id=uid, channel_id=ch.id))
    await db_session.commit()

    row = await db_session.get(UserCatalogHiddenChannel, (uid, ch.id))
    assert row is not None
    assert row.hidden_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_read_post_insert_and_fk_cascade(db_session, seed_user) -> None:
    from sqlalchemy import func, select

    from shared.models import Channel, Post, UserReadPost

    uid = await seed_user(tg_user_id=902)
    ch = Channel(tg_chat_id=900002, username="x_read", title="XR")
    db_session.add(ch)
    await db_session.commit()
    p = Post(channel_id=ch.id, tg_message_id=1, posted_at=datetime.now(tz=timezone.utc))
    db_session.add(p)
    await db_session.commit()
    post_id = p.id

    db_session.add(UserReadPost(user_id=uid, post_id=post_id))
    await db_session.commit()
    row = await db_session.get(UserReadPost, (uid, post_id))
    assert row is not None
    assert row.read_at is not None

    # FK ON DELETE CASCADE: removing the post removes the read row.
    await db_session.delete(p)
    await db_session.commit()
    remaining = await db_session.scalar(
        select(func.count())
        .select_from(UserReadPost)
        .where(UserReadPost.post_id == post_id)
    )
    assert remaining == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_channel_category_link_insert_and_fk_cascade(db_session) -> None:
    from sqlalchemy import func, select

    from shared.models import Channel, ChannelCategoryLink

    ch = Channel(tg_chat_id=900100, username="x_cat_link", title="XC")
    db_session.add(ch)
    await db_session.commit()
    channel_id = ch.id

    db_session.add_all([
        ChannelCategoryLink(channel_id=channel_id, category="news"),
        ChannelCategoryLink(channel_id=channel_id, category="tech"),
    ])
    await db_session.commit()

    cats = await db_session.scalars(
        select(ChannelCategoryLink.category)
        .where(ChannelCategoryLink.channel_id == channel_id)
        .order_by(ChannelCategoryLink.category)
    )
    assert list(cats) == ["news", "tech"]

    # FK ON DELETE CASCADE: removing the channel removes its category links.
    await db_session.delete(ch)
    await db_session.commit()
    remaining = await db_session.scalar(
        select(func.count())
        .select_from(ChannelCategoryLink)
        .where(ChannelCategoryLink.channel_id == channel_id)
    )
    assert remaining == 0
