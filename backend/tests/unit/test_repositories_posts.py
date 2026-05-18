"""Unit tests for shared.repositories.posts.upsert_post — covers both
solo posts and Telegram media-group append behaviour."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock


def _scalar_result(value):
    r = MagicMock()
    r.scalar = MagicMock(return_value=value)
    return r


def _scalar_one_or_none(value):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=value)
    return r


def _scalar_one(value):
    r = MagicMock()
    r.scalar_one = MagicMock(return_value=value)
    return r


def test_upsert_post_solo_inserts_and_returns_new_id():
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_result(42),                                       # INSERT Post
        MagicMock(),                                              # INSERT Media
    ])
    post = {"channel_id": 1, "tg_message_id": 10, "tg_grouped_id": None}
    media = [{"type": "photo", "tg_file_id": "p1", "position": 0}]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id == 42
    assert session.execute.await_count == 2


def test_upsert_post_solo_duplicate_returns_none_and_skips_media():
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_result(None))
    post = {"channel_id": 1, "tg_message_id": 10, "tg_grouped_id": None}
    media = [{"type": "photo", "tg_file_id": "p1", "position": 0}]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id is None
    assert session.execute.await_count == 1  # only the INSERT attempt


def test_upsert_post_group_no_existing_inserts_new():
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(None),    # SELECT existing — none
        _scalar_result(101),          # INSERT Post returning new id
        MagicMock(),                  # INSERT Media
    ])
    post = {"channel_id": 1, "tg_message_id": 10, "tg_grouped_id": 999}
    media = [{"type": "photo", "tg_file_id": "p1", "position": 0}]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id == 101
    assert session.execute.await_count == 3


def test_upsert_post_group_with_existing_appends_media_and_returns_existing_id():
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(101),     # SELECT existing — id=101
        _scalar_one(0),               # SELECT max(position) for that post
        MagicMock(),                  # INSERT Media (with position=1)
    ])
    post = {"channel_id": 1, "tg_message_id": 11, "tg_grouped_id": 999}
    media = [{"type": "photo", "tg_file_id": "p2", "position": 0}]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id == 101  # existing Post id, not the duplicate
    # No INSERT Post — only SELECT existing, SELECT max(pos), INSERT Media.
    assert session.execute.await_count == 3
    # Verify the third call (INSERT Media) used position=1 (max=0 + 1).
    third_call = session.execute.await_args_list[2]
    inserted_rows = third_call.args[1]
    assert inserted_rows[0]["post_id"] == 101
    assert inserted_rows[0]["position"] == 1


def test_upsert_post_group_with_existing_and_empty_media_is_noop():
    """Edge: group event with no media (text-only? shouldn't happen for
    Telegram albums, but be defensive)."""
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(101),
    ])
    post = {"channel_id": 1, "tg_message_id": 11, "tg_grouped_id": 999}

    new_id = asyncio.run(upsert_post(session, post, []))

    assert new_id == 101
    assert session.execute.await_count == 1
