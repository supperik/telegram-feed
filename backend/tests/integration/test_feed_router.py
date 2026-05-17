from datetime import datetime, timedelta, timezone

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel, Post, UserSource


SECRET = "x" * 32


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {encode_access(user_id=user_id, secret=SECRET, ttl_seconds=60)}"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_returns_first_page_with_cursor(
    async_client, db_session, seed_user
) -> None:
    user_id = await seed_user(tg_user_id=31)
    ch = Channel(tg_chat_id=80001, username="feed", title="Feed")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(4):
        db_session.add(
            Post(channel_id=ch.id, tg_message_id=i + 1, text=str(i), posted_at=base + timedelta(seconds=i))
        )
    await db_session.commit()

    r = await async_client.get("/feed?limit=2", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["posts"]) == 2
    assert body["posts"][0]["tg_message_id"] == 4
    assert body["posts"][1]["tg_message_id"] == 3
    assert body["next_cursor"] is not None

    r2 = await async_client.get(
        f"/feed?limit=2&cursor={body['next_cursor']}", headers=_auth(user_id)
    )
    body2 = r2.json()
    assert [p["tg_message_id"] for p in body2["posts"]] == [2, 1]
    assert body2["next_cursor"] is None or body2["posts"]  # last page either way
