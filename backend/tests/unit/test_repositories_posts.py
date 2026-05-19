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
        _scalars_all(["p1"]),         # SELECT existing tg_file_ids on that post
        _scalar_one(0),               # SELECT max(position) for that post
        MagicMock(),                  # INSERT Media (with position=1)
    ])
    post = {"channel_id": 1, "tg_message_id": 11, "tg_grouped_id": 999}
    media = [{"type": "photo", "tg_file_id": "p2", "position": 0}]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id == 101  # existing Post id, not the duplicate
    # SELECT existing, SELECT present tg_file_ids, SELECT max(pos), INSERT Media.
    assert session.execute.await_count == 4
    # Verify the INSERT used position=1 (max=0 + 1).
    insert_call = session.execute.await_args_list[3]
    inserted_rows = insert_call.args[1]
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


def _scalars_all(values):
    r = MagicMock()
    inner = MagicMock()
    inner.all = MagicMock(return_value=values)
    r.scalars = MagicMock(return_value=inner)
    return r


def test_upsert_post_group_skips_media_already_present_by_tg_file_id():
    """Catchup re-runs after restart and feeds the same album tail
    message back into upsert_post. The append branch MUST dedupe by
    tg_file_id so the existing Media row is not duplicated."""
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(101),       # SELECT existing Post by grouped_id
        _scalars_all(["p2"]),           # SELECT existing tg_file_ids on that post
        # No max(pos) query, no INSERT Media — every media is a duplicate.
    ])
    post = {"channel_id": 1, "tg_message_id": 11, "tg_grouped_id": 999}
    media = [{"type": "photo", "tg_file_id": "p2", "position": 0}]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id == 101
    assert session.execute.await_count == 2  # only the two SELECTs


def test_upsert_post_group_appends_only_genuinely_new_media():
    """Mixed case: some media already exist (skip), some are new (append
    with continuous positions starting from max+1)."""
    from shared.repositories.posts import upsert_post

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _scalar_one_or_none(101),       # SELECT existing Post
        _scalars_all(["p1", "p2"]),     # already have p1 and p2
        _scalar_one(1),                 # SELECT max(position) → 1
        MagicMock(),                    # INSERT Media (only p3)
    ])
    post = {"channel_id": 1, "tg_message_id": 12, "tg_grouped_id": 999}
    media = [
        {"type": "photo", "tg_file_id": "p1", "position": 0},
        {"type": "photo", "tg_file_id": "p2", "position": 1},
        {"type": "photo", "tg_file_id": "p3", "position": 2},
    ]

    new_id = asyncio.run(upsert_post(session, post, media))

    assert new_id == 101
    assert session.execute.await_count == 4
    insert_call = session.execute.await_args_list[3]
    inserted_rows = insert_call.args[1]
    assert len(inserted_rows) == 1
    assert inserted_rows[0]["tg_file_id"] == "p3"
    assert inserted_rows[0]["post_id"] == 101
    assert inserted_rows[0]["position"] == 2  # max(1) + 1
