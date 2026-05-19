"""Unit tests for ingester.merge_existing_albums: refetch Telegram
messages for posts ingested before tg_grouped_id existed, then merge
sibling Post-rows into a single Post with reassigned media."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


@asynccontextmanager
async def _session_cm(session):
    yield session


def _session_factory(session):
    f = MagicMock()
    f.side_effect = lambda *a, **kw: _session_cm(session)
    return f


def _result_with_all(rows):
    r = MagicMock()
    r.all = MagicMock(return_value=rows)
    return r


def _result_scalar_one(value):
    r = MagicMock()
    r.scalar_one = MagicMock(return_value=value)
    return r


def _result_scalars_all(values):
    r = MagicMock()
    inner = MagicMock()
    inner.all = MagicMock(return_value=values)
    r.scalars = MagicMock(return_value=inner)
    return r


def test_merge_no_targets_returns_zero():
    from ingester import merge_existing_albums as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock()
    fake_client.get_messages = AsyncMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([]))
    sf = _session_factory(session)

    n = asyncio.run(mod.merge_existing_albums(fake_client, sf))

    assert n == 0
    fake_client.get_entity.assert_not_awaited()
    fake_client.get_messages.assert_not_awaited()


def test_merge_tags_solo_with_grouped_id_without_deleting():
    """A Post that was the only sibling we ingested for an album just
    gets tg_grouped_id set — no merge needed, no Posts deleted."""
    from ingester import merge_existing_albums as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    msg = MagicMock(id=10)
    msg.grouped_id = 555
    fake_client.get_messages = AsyncMock(return_value=[msg])

    session = MagicMock()
    session.commit = AsyncMock()
    # Targets: one post (post_id=100, tg_message_id=10, channel_id=7, tg_chat_id=-100)
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(100, 10, 7, -100)]),
        MagicMock(),  # UPDATE Post SET tg_grouped_id
    ])
    sf = _session_factory(session)

    n = asyncio.run(mod.merge_existing_albums(fake_client, sf))

    assert n == 1  # 1 post tagged
    # The UPDATE was on post id=100 setting tg_grouped_id=555.
    update_call = session.execute.await_args_list[1]
    compiled = update_call.args[0].compile()
    assert compiled.params.get("tg_grouped_id") == 555


def test_merge_three_sibling_posts_into_one_with_three_media():
    """Three Post-rows for one album: head (min msg.id) stays; the
    other two have their media reassigned to head and are DELETEd."""
    from ingester import merge_existing_albums as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    # Telegram replies: three msgs all with grouped_id=999
    msgs = []
    for mid in (10, 11, 12):
        m = MagicMock(id=mid)
        m.grouped_id = 999
        msgs.append(m)
    fake_client.get_messages = AsyncMock(return_value=msgs)

    session = MagicMock()
    session.commit = AsyncMock()
    # Sequence per merge group:
    #   1) targets SELECT
    #   2) SELECT max(position) for head_post
    #   3..N) SELECT media ids for each tail post
    #   ...   UPDATE Media (move to head + new position)
    #   ...   DELETE Posts (tail)
    #   ...   UPDATE Post tg_grouped_id on head
    # We simulate the actual sequence: targets → max_pos → media of tail1 → move 1 → media of tail2 → move 1 → delete → tag.
    # For simplicity, allow any number of calls; return sensible results.
    media_call_count = {"n": 0}

    def execute_side_effect(*args, **kwargs):
        media_call_count["n"] += 1
        n = media_call_count["n"]
        if n == 1:
            return _result_with_all([
                (100, 10, 7, -100),
                (101, 11, 7, -100),
                (102, 12, 7, -100),
            ])
        if n == 2:
            return _result_scalar_one(0)  # max(position) on head=0 (one media there)
        if n == 3:
            return _result_scalars_all(["headfile"])  # existing tg_file_ids on head
        if n == 4:
            return _result_with_all([(2001, "tailA")])  # tail post 101 media
        if n == 5:
            return _result_with_all([(2002, "tailB")])  # tail post 102 media
        # remaining executions (updates/deletes) — return generic MagicMock.
        return MagicMock()

    session.execute = AsyncMock(side_effect=execute_side_effect)
    sf = _session_factory(session)

    n = asyncio.run(mod.merge_existing_albums(fake_client, sf))

    assert n == 2  # two posts merged-away
    # Verify a DELETE FROM posts WHERE id IN (...) was issued for {101, 102}.
    seen_deletes = []
    seen_tag = None
    for call in session.execute.await_args_list:
        stmt = call.args[0]
        compiled_str = str(stmt)
        if "DELETE FROM posts" in compiled_str:
            seen_deletes.append(stmt)
        if "UPDATE posts" in compiled_str and "tg_grouped_id" in compiled_str:
            seen_tag = stmt
    assert seen_deletes, "expected a DELETE FROM posts"
    assert seen_tag is not None, "expected an UPDATE posts SET tg_grouped_id"


def test_merge_handles_deleted_telegram_message_gracefully():
    """If get_messages returns None for an id, that post is skipped
    (left as solo with tg_grouped_id NULL)."""
    from ingester import merge_existing_albums as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_client.get_messages = AsyncMock(return_value=[None])

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([(100, 10, 7, -100)]))
    sf = _session_factory(session)

    n = asyncio.run(mod.merge_existing_albums(fake_client, sf))

    assert n == 0
    # No UPDATE/DELETE — only the initial SELECT.
    assert session.execute.await_count == 1


def test_merge_deletes_tail_media_already_present_on_head_instead_of_moving():
    """If the tail post has a Media row with a tg_file_id that already
    lives on the head post (legacy data accidentally ingested twice),
    moving it would violate the new UNIQUE(post_id, tg_file_id) index.
    The merge must DELETE such a duplicate row instead of UPDATE-ing it."""
    from ingester import merge_existing_albums as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    msgs = []
    for mid in (10, 11):
        m = MagicMock(id=mid)
        m.grouped_id = 999
        msgs.append(m)
    fake_client.get_messages = AsyncMock(return_value=msgs)

    session = MagicMock()
    session.commit = AsyncMock()
    call = {"n": 0}
    seen = {"updates": 0, "deletes_media": 0}

    def execute_side_effect(*args, **kwargs):
        call["n"] += 1
        n = call["n"]
        if n == 1:
            # targets: two siblings — head id=100/msg=10, tail id=101/msg=11
            return _result_with_all([(100, 10, 7, -100), (101, 11, 7, -100)])
        if n == 2:
            return _result_scalar_one(0)  # max(position) on head
        if n == 3:
            # NEW: head's existing tg_file_ids
            return _result_scalars_all(["A"])
        if n == 4:
            # tail media: (id, tg_file_id) — one is duplicate, one is new.
            return _result_with_all([(2001, "A"), (2002, "B")])
        # follow-up calls: classify by SQL text
        stmt = args[0]
        s = str(stmt)
        if "UPDATE media" in s:
            seen["updates"] += 1
        elif "DELETE FROM media" in s:
            seen["deletes_media"] += 1
        return MagicMock()

    session.execute = AsyncMock(side_effect=execute_side_effect)
    sf = _session_factory(session)

    n = asyncio.run(mod.merge_existing_albums(fake_client, sf))

    assert n == 1  # one tail post merged-away
    # Duplicate row (id=2001, tg_file_id="A") must be DELETEd; the new row
    # (id=2002, tg_file_id="B") must be UPDATEd onto the head.
    assert seen["deletes_media"] == 1
    assert seen["updates"] == 1


def test_merge_continues_when_get_entity_fails():
    from ingester import merge_existing_albums as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(side_effect=Exception("no access"))
    fake_client.get_messages = AsyncMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([(100, 10, 7, -100)]))
    sf = _session_factory(session)

    n = asyncio.run(mod.merge_existing_albums(fake_client, sf))

    assert n == 0
    fake_client.get_messages.assert_not_awaited()
