"""Unit tests for ingester.backfill_text_html: refetch posts whose
text_html is NULL and recompute it from Telegram entities."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from telethon.tl.types import MessageEntityBold


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


def test_backfill_text_html_no_targets():
    """No posts need backfilling → no Telethon calls, returns 0."""
    from ingester import backfill_text_html as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock()
    fake_client.get_messages = AsyncMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([]))
    sf = _session_factory(session)

    result = asyncio.run(mod.backfill_text_html(fake_client, sf))

    assert result == 0
    fake_client.get_entity.assert_not_awaited()
    fake_client.get_messages.assert_not_awaited()


def test_backfill_text_html_updates_post_using_telegram_entities():
    """A single post with text_html=NULL gets re-fetched from Telegram and
    UPDATEd with entities-derived HTML."""
    from ingester import backfill_text_html as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    msg = MagicMock(id=42)
    msg.message = "hello bold"
    msg.text = "hello bold"
    msg.entities = [MessageEntityBold(offset=6, length=4)]
    fake_client.get_messages = AsyncMock(return_value=[msg])

    session = MagicMock()
    session.commit = AsyncMock()
    # Targets: (post_id=100, tg_message_id=42, tg_chat_id=-100, text="hello bold")
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(100, 42, -100, "hello bold")]),
        MagicMock(),  # UPDATE result
    ])
    sf = _session_factory(session)

    result = asyncio.run(mod.backfill_text_html(fake_client, sf))

    fake_client.get_entity.assert_awaited_once_with(-100)
    fake_client.get_messages.assert_awaited_once()
    # UPDATE was issued with the entities-derived HTML.
    update_call = session.execute.await_args_list[1]
    stmt = update_call.args[0]
    # The compiled statement's parameters include text_html.
    compiled = stmt.compile()
    params = compiled.params
    assert "<strong>bold</strong>" in params["text_html"]
    assert result == 1


def test_backfill_text_html_falls_back_to_escaped_text_when_message_deleted():
    """If get_messages returns None for an ID (message deleted in Telegram),
    the stored plain text is HTML-escaped and used as text_html so the post
    stays readable."""
    from ingester import backfill_text_html as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_client.get_messages = AsyncMock(return_value=[None])

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(100, 42, -100, "<plain>")]),
        MagicMock(),
    ])
    sf = _session_factory(session)

    result = asyncio.run(mod.backfill_text_html(fake_client, sf))

    update_call = session.execute.await_args_list[1]
    compiled = update_call.args[0].compile()
    assert compiled.params["text_html"] == "&lt;plain&gt;"
    assert result == 1


def test_backfill_text_html_continues_when_get_entity_fails():
    """If get_entity raises, that channel is skipped and the next one is
    processed."""
    from ingester import backfill_text_html as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(side_effect=Exception("no access_hash"))
    fake_client.get_messages = AsyncMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([
        (100, 42, -100, "a"),
        (101, 43, -200, "b"),
    ]))
    sf = _session_factory(session)

    result = asyncio.run(mod.backfill_text_html(fake_client, sf))

    assert fake_client.get_entity.await_count == 2
    fake_client.get_messages.assert_not_awaited()
    assert result == 0


def test_backfill_text_html_batches_large_channel_into_get_messages_calls():
    """Channels with >100 posts are batched into multiple get_messages calls."""
    from ingester import backfill_text_html as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    # 150 posts in one channel.
    targets = [(1000 + i, i + 1, -100, f"t{i}") for i in range(150)]

    # get_messages echoes a fake message per id so each post gets a non-None
    # message — text_html becomes escape("t{i}").
    def _fake_msg(i):
        m = MagicMock(id=i + 1)
        m.message = f"t{i}"
        m.text = f"t{i}"
        m.entities = None
        return m

    call_count = {"n": 0}

    async def fake_get_messages(_entity, ids):
        call_count["n"] += 1
        return [_fake_msg(i - 1) for i in ids]

    fake_client.get_messages = AsyncMock(side_effect=fake_get_messages)

    session = MagicMock()
    session.commit = AsyncMock()
    # 1 targets fetch + 150 UPDATEs
    session.execute = AsyncMock(side_effect=[_result_with_all(targets)]
                                 + [MagicMock() for _ in range(150)])
    sf = _session_factory(session)

    result = asyncio.run(mod.backfill_text_html(fake_client, sf))

    # Default batch=100 → 2 calls for 150 ids.
    assert call_count["n"] == 2
    assert result == 150
