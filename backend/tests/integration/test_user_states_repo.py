from datetime import datetime, timezone

import pytest

from shared.models import Channel, Post, UserHiddenChannel, UserHiddenPost, UserSavedPost
from shared.repositories.user_states import (
    hide_channel,
    hide_post,
    save_post,
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
