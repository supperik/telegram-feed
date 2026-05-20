from datetime import datetime, timezone

import pytest

from shared.models import Channel, Post
from shared.repositories.user_read_posts import bulk_mark_read


async def _seed_posts(db_session, *, channel_tg_id, username, count):
    ch = Channel(tg_chat_id=channel_tg_id, username=username, title=username.upper())
    db_session.add(ch)
    await db_session.commit()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    posts = [
        Post(channel_id=ch.id, tg_message_id=i + 1, posted_at=base) for i in range(count)
    ]
    db_session.add_all(posts)
    await db_session.commit()
    return [p.id for p in posts]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_mark_read_inserts_and_returns_count(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=6001)
    # Posts in a channel the user is NOT subscribed to — marking still works.
    post_ids = await _seed_posts(db_session, channel_tg_id=130001, username="rr_a", count=3)

    marked = await bulk_mark_read(db_session, user_id=uid, post_ids=post_ids)
    await db_session.commit()
    assert marked == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_mark_read_is_idempotent_on_overlap(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=6002)
    post_ids = await _seed_posts(db_session, channel_tg_id=130002, username="rr_b", count=3)

    first = await bulk_mark_read(db_session, user_id=uid, post_ids=post_ids)
    await db_session.commit()
    assert first == 3

    new_id = (await _seed_posts(db_session, channel_tg_id=130003, username="rr_c", count=1))[0]
    second = await bulk_mark_read(
        db_session, user_id=uid, post_ids=[post_ids[0], post_ids[1], new_id]
    )
    await db_session.commit()
    assert second == 1  # only the genuinely new id is inserted

    third = await bulk_mark_read(db_session, user_id=uid, post_ids=post_ids)
    await db_session.commit()
    assert third == 0  # fully repeated batch inserts nothing


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_mark_read_empty_list_returns_zero(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=6003)
    assert await bulk_mark_read(db_session, user_id=uid, post_ids=[]) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_mark_read_dedups_within_batch(db_session, seed_user) -> None:
    uid = await seed_user(tg_user_id=6004)
    post_ids = await _seed_posts(db_session, channel_tg_id=130004, username="rr_d", count=1)
    marked = await bulk_mark_read(
        db_session, user_id=uid, post_ids=[post_ids[0], post_ids[0], post_ids[0]]
    )
    await db_session.commit()
    assert marked == 1
