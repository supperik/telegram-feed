from datetime import datetime, timedelta, timezone

import pytest

from shared.models import Channel, Media, Post, UserSavedPost, UserSource
from shared.repositories.feed import FeedPostRow, fetch_feed_page


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_keyset_returns_newest_first_and_paginates(
    db_session, seed_user
) -> None:
    user_id = await seed_user(tg_user_id=21)
    ch = Channel(tg_chat_id=70001, username="chan", title="Chan")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    await db_session.commit()

    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    posts = []
    for i in range(5):
        p = Post(
            channel_id=ch.id,
            tg_message_id=100 + i,
            text=f"post {i}",
            posted_at=base + timedelta(minutes=i),
        )
        db_session.add(p)
        posts.append(p)
    await db_session.commit()
    # Save the middle one to verify annotation.
    db_session.add(UserSavedPost(user_id=user_id, post_id=posts[2].id))
    await db_session.commit()

    page1 = await fetch_feed_page(
        db_session,
        user_id=user_id,
        cursor_posted_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        cursor_post_id=0,
        limit=3,
    )
    assert [r.tg_message_id for r in page1] == [104, 103, 102]
    assert next(r for r in page1 if r.tg_message_id == 102).is_saved is True
    assert all(r.channel_tg_chat_id == 70001 for r in page1)

    last = page1[-1]
    page2 = await fetch_feed_page(
        db_session,
        user_id=user_id,
        cursor_posted_at=last.posted_at,
        cursor_post_id=last.post_id,
        limit=3,
    )
    assert [r.tg_message_id for r in page2] == [101, 100]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_skips_hidden_channels_and_posts(db_session, seed_user) -> None:
    from shared.models import UserHiddenChannel, UserHiddenPost

    user_id = await seed_user(tg_user_id=22)
    ch1 = Channel(tg_chat_id=70010, username="c1", title="C1")
    ch2 = Channel(tg_chat_id=70011, username="c2", title="C2")
    db_session.add_all([ch1, ch2])
    await db_session.commit()
    db_session.add_all(
        [
            UserSource(user_id=user_id, channel_id=ch1.id),
            UserSource(user_id=user_id, channel_id=ch2.id),
        ]
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    p1 = Post(channel_id=ch1.id, tg_message_id=1, text="ok", posted_at=base)
    p2 = Post(channel_id=ch1.id, tg_message_id=2, text="hidden post", posted_at=base + timedelta(seconds=1))
    p3 = Post(channel_id=ch2.id, tg_message_id=3, text="from hidden channel", posted_at=base + timedelta(seconds=2))
    db_session.add_all([p1, p2, p3])
    await db_session.commit()

    db_session.add_all(
        [
            UserHiddenPost(user_id=user_id, post_id=p2.id),
            UserHiddenChannel(user_id=user_id, channel_id=ch2.id),
        ]
    )
    await db_session.commit()

    page = await fetch_feed_page(
        db_session,
        user_id=user_id,
        cursor_posted_at=datetime(9999, 12, 31, tzinfo=timezone.utc),
        cursor_post_id=0,
        limit=10,
    )
    assert [r.tg_message_id for r in page] == [1]
