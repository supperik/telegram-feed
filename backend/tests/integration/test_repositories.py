import asyncio
from datetime import datetime, timezone

import pytest


@pytest.mark.integration
def test_upsert_channel_inserts_then_returns_existing(configured_env, pg_container):
    async def run():
        from shared.db import make_engine, make_session_factory
        from shared.repositories.channels import upsert_channel

        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            ch1 = await upsert_channel(s, tg_chat_id=-100200001, username="test1", title="T1")
            await s.commit()
            assert ch1.id is not None
            id1 = ch1.id
            ch2 = await upsert_channel(s, tg_chat_id=-100200001, username="test1", title="T1 RENAMED")
            await s.commit()
            assert ch2.id == id1
            # upsert does not overwrite title on existing — it returns existing as-is.
            assert ch2.title == "T1"
        await engine.dispose()

    asyncio.run(run())


@pytest.mark.integration
def test_increment_decrement_ref_count(configured_env, pg_container):
    async def run():
        from shared.db import make_engine, make_session_factory
        from shared.repositories.channels import (
            upsert_channel, increment_ref_count, decrement_ref_count, get_subscription
        )

        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            ch = await upsert_channel(s, tg_chat_id=-100200002, username="testrc", title="RC")
            await s.commit()
            sub = await increment_ref_count(s, channel_id=ch.id)
            await s.commit()
            assert sub.ref_count == 1
            assert sub.status == "pending_backfill"

            await increment_ref_count(s, channel_id=ch.id)
            await s.commit()
            sub = await get_subscription(s, channel_id=ch.id)
            assert sub.ref_count == 2

            await decrement_ref_count(s, channel_id=ch.id)
            await decrement_ref_count(s, channel_id=ch.id)
            await s.commit()
            sub = await get_subscription(s, channel_id=ch.id)
            assert sub.ref_count == 0

            # Decrement below zero is clamped.
            await decrement_ref_count(s, channel_id=ch.id)
            await s.commit()
            sub = await get_subscription(s, channel_id=ch.id)
            assert sub.ref_count == 0
        await engine.dispose()

    asyncio.run(run())


@pytest.mark.integration
def test_join_queue_pop_and_mark(configured_env, pg_container):
    async def run():
        from sqlalchemy import insert, select
        from shared.db import make_engine, make_session_factory
        from shared.models import ChannelJoinQueue
        from shared.repositories.join_queue import (
            pop_pending_join_request, mark_join_done, mark_join_failed
        )
        from shared.repositories.channels import upsert_channel

        engine = make_engine(pg_container["async_url"])
        sf = make_session_factory(engine)
        async with sf() as s:
            # Empty queue → None.
            row = await pop_pending_join_request(s)
            assert row is None

            # Insert two pending rows.
            await s.execute(insert(ChannelJoinQueue).values(
                channel_username="alpha", status="pending"
            ))
            await s.execute(insert(ChannelJoinQueue).values(
                channel_username="bravo", status="pending"
            ))
            await s.commit()

            popped = await pop_pending_join_request(s)
            await s.commit()
            assert popped is not None
            assert popped.channel_username == "alpha"  # FIFO by created_at
            assert popped.status == "in_progress"

            # The next pop returns bravo, not alpha.
            popped2 = await pop_pending_join_request(s)
            await s.commit()
            assert popped2.channel_username == "bravo"

            # Mark alpha done.
            ch = await upsert_channel(s, tg_chat_id=-100200003, username="alpha", title="Alpha")
            await s.commit()
            await mark_join_done(s, queue_id=popped.id, channel_id=ch.id)
            await s.commit()
            res = await s.execute(select(ChannelJoinQueue).where(ChannelJoinQueue.id == popped.id))
            r = res.scalar_one()
            assert r.status == "done"
            assert r.channel_id == ch.id

            # Mark bravo failed.
            await mark_join_failed(s, queue_id=popped2.id, error_reason="username_not_occupied")
            await s.commit()
            res = await s.execute(select(ChannelJoinQueue).where(ChannelJoinQueue.id == popped2.id))
            r = res.scalar_one()
            assert r.status == "failed"
            assert r.error_reason == "username_not_occupied"
        await engine.dispose()

    asyncio.run(run())
