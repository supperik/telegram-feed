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
