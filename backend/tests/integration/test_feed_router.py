from datetime import datetime, timedelta, timezone

import pytest

from shared.auth.jwt import encode_access
from shared.models import Channel, Media, Post, UserSource


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
    # tg_chat_id is required by the TMA to build t.me/c/<id>/<msg> deep links
    # for private channels (no username); we surface it on every feed post.
    assert body["posts"][0]["channel"]["tg_chat_id"] == 80001
    assert body["next_cursor"] is not None

    r2 = await async_client.get(
        f"/feed?limit=2&cursor={body['next_cursor']}", headers=_auth(user_id)
    )
    body2 = r2.json()
    assert [p["tg_message_id"] for p in body2["posts"]] == [2, 1]
    assert body2["next_cursor"] is None or body2["posts"]  # last page either way


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_returns_fresh_post_within_cache_window(
    async_client, db_session, seed_user
) -> None:
    """Repro for telegram-feed-6rw: a post inserted between two /feed calls
    within the Redis cache TTL window must still appear in the second call —
    the 'Refresh' behaviour expected by users in the TMA.
    """
    user_id = await seed_user(tg_user_id=32)
    ch = Channel(tg_chat_id=80100, username="refresh_window", title="Refresh")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db_session.add(
        Post(channel_id=ch.id, tg_message_id=1, text="old", posted_at=base)
    )
    await db_session.commit()

    r1 = await async_client.get("/feed", headers=_auth(user_id))
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["posts"]) == 1

    db_session.add(
        Post(
            channel_id=ch.id,
            tg_message_id=2,
            text="fresh",
            posted_at=base + timedelta(seconds=10),
        )
    )
    await db_session.commit()

    r2 = await async_client.get("/feed", headers=_auth(user_id))
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert len(body["posts"]) == 2, (
        "Refresh must show the freshly inserted post even within the "
        f"Redis cache TTL window, got: {body}"
    )
    assert body["posts"][0]["tg_message_id"] == 2
    assert body["posts"][1]["tg_message_id"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_returns_invite_url_for_private_channel(
    async_client, db_session, seed_user
) -> None:
    """Channel with invite_hash='abc123' must surface invite_url='https://t.me/+abc123'.

    TMA needs an opaque invite URL to render the «Join private channel» CTA;
    the raw hash must never leak — only the t.me/+ link.
    """
    user_id = await seed_user(tg_user_id=8001)
    ch = Channel(
        tg_chat_id=80201,
        username=None,
        title="Private",
        invite_hash="abc123",
    )
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    db_session.add(
        Post(
            channel_id=ch.id,
            tg_message_id=1,
            text="hi",
            posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    r = await async_client.get("/feed", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["posts"], body
    channel = body["posts"][0]["channel"]
    assert channel["invite_url"] == "https://t.me/+abc123"
    # The raw hash must NEVER be exposed by the API.
    assert "invite_hash" not in channel


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_returns_null_invite_url_when_no_hash(
    async_client, db_session, seed_user
) -> None:
    """Public channel without invite_hash must return invite_url=None."""
    user_id = await seed_user(tg_user_id=8002)
    ch = Channel(tg_chat_id=80202, username="public_ch", title="Public")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    db_session.add(
        Post(
            channel_id=ch.id,
            tg_message_id=1,
            text="hi",
            posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    r = await async_client.get("/feed", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["posts"], body
    assert body["posts"][0]["channel"]["invite_url"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_returns_has_video_file_true_when_storage_key_set(
    async_client, db_session, seed_user
) -> None:
    """Video media with non-null video_storage_key must report has_video_file=True."""
    user_id = await seed_user(tg_user_id=8003)
    ch = Channel(tg_chat_id=80203, username="vidch", title="VidCh")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    post = Post(
        channel_id=ch.id,
        tg_message_id=1,
        text="clip",
        posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(post)
    await db_session.commit()
    db_session.add(
        Media(
            post_id=post.id,
            type="video",
            storage_key="photos/1/thumb.jpg",
            video_storage_key="videos/1/clip.mp4",
            position=0,
        )
    )
    await db_session.commit()

    r = await async_client.get("/feed", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["posts"], body
    media = body["posts"][0]["media"]
    assert len(media) == 1
    assert media[0]["type"] == "video"
    assert media[0]["has_video_file"] is True
    # Raw key must not leak.
    assert "video_storage_key" not in media[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_feed_returns_has_video_file_false_when_no_video_storage_key(
    async_client, db_session, seed_user
) -> None:
    """Video media without video_storage_key must report has_video_file=False."""
    user_id = await seed_user(tg_user_id=8004)
    ch = Channel(tg_chat_id=80204, username="vidch2", title="VidCh2")
    db_session.add(ch)
    await db_session.commit()
    db_session.add(UserSource(user_id=user_id, channel_id=ch.id))
    post = Post(
        channel_id=ch.id,
        tg_message_id=1,
        text="thumb only",
        posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(post)
    await db_session.commit()
    db_session.add(
        Media(
            post_id=post.id,
            type="video",
            storage_key="photos/2/thumb.jpg",
            video_storage_key=None,
            position=0,
        )
    )
    await db_session.commit()

    r = await async_client.get("/feed", headers=_auth(user_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["posts"], body
    media = body["posts"][0]["media"]
    assert len(media) == 1
    assert media[0]["type"] == "video"
    assert media[0]["has_video_file"] is False
