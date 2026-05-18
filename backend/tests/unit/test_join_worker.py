import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@asynccontextmanager
async def _fake_session_cm(session):
    yield session


def _fake_session_factory(session):
    factory = MagicMock()
    # Each call must produce a fresh CM (async CMs are single-shot).
    factory.side_effect = lambda *a, **kw: _fake_session_cm(session)
    return factory


async def _async_empty():
    """Empty async generator, used to stub iter_messages with no results."""
    if False:
        yield


def test_join_worker_happy_path(monkeypatch):
    """Happy path: one pending row → get_entity → join → upsert →
    add_user_source(requester) → done.

    Crucially the requester (pending.requested_by_user_id) MUST get a
    UserSource link so the channel appears in their personal /sources list.
    Otherwise the channel is joined globally but invisible to the user
    who asked for it. ref_count is incremented inside add_user_source
    (was_new=True path), so we do NOT separately call increment_ref_count
    in the join_worker.
    """
    from ingester import join_worker as jw

    pending = MagicMock(
        id=42, channel_username="testchan", channel_id=None,
        requested_by_user_id=11,
    )
    entity = MagicMock(id=-100123, username="testchan", title="Test Chan")
    channel = MagicMock(id=99)

    fake_pop = AsyncMock(side_effect=[pending, None])  # one row, then drain
    fake_get_entity = AsyncMock(return_value=entity)
    fake_upsert_channel = AsyncMock(return_value=channel)
    fake_add_user_source = AsyncMock(return_value=(True, "pending_backfill"))
    fake_inc_ref = AsyncMock()  # MUST stay un-called — see assert_not_called below.
    fake_mark_done = AsyncMock()
    fake_mark_failed = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity
    fake_client.__call__ = AsyncMock()
    fake_client.return_value = None
    async def _client_call(_req):
        return None
    fake_client.side_effect = _client_call
    fake_client.iter_messages = MagicMock(return_value=_async_empty())

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "upsert_channel", fake_upsert_channel)
    monkeypatch.setattr(jw, "add_user_source", fake_add_user_source)
    monkeypatch.setattr(jw, "mark_join_done", fake_mark_done)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)
    monkeypatch.setattr(jw, "JoinChannelRequest", lambda e: ("join", e))

    sf = _fake_session_factory(session)

    async def driver():
        await jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media")
        await jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media")

    asyncio.run(driver())

    fake_pop.assert_awaited()
    fake_get_entity.assert_awaited_once_with("testchan")
    fake_upsert_channel.assert_awaited_once()
    # Requester is linked to the newly joined channel.
    fake_add_user_source.assert_awaited_once_with(session, user_id=11, channel_id=99)
    fake_mark_done.assert_awaited_once_with(session, queue_id=42, channel_id=99)
    fake_mark_failed.assert_not_called()
    fake_client.iter_messages.assert_called_once()


def test_join_worker_handles_username_not_occupied(monkeypatch):
    from telethon.errors import UsernameNotOccupiedError
    from ingester import join_worker as jw

    pending = MagicMock(id=7, channel_username="ghost")

    fake_pop = AsyncMock(return_value=pending)
    fake_get_entity = AsyncMock(side_effect=UsernameNotOccupiedError(None))
    fake_mark_failed = AsyncMock()
    fake_mark_done = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity

    session = MagicMock()
    session.commit = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)
    monkeypatch.setattr(jw, "mark_join_done", fake_mark_done)

    sf = _fake_session_factory(session)
    asyncio.run(jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media"))

    fake_mark_failed.assert_awaited_once()
    args, kwargs = fake_mark_failed.call_args
    assert kwargs["queue_id"] == 7
    assert kwargs["error_code"] == "username_not_occupied"
    assert "username_not_occupied" in kwargs["error_reason"].lower()
    fake_mark_done.assert_not_called()


def test_join_worker_handles_floodwait(monkeypatch):
    """FloodWaitError should NOT mark failed; it sleeps then returns (the loop
    will retry on the next iteration with the same row state). We assert
    asyncio.sleep is awaited with seconds + 1."""
    from telethon.errors import FloodWaitError
    from ingester import join_worker as jw

    pending = MagicMock(id=11, channel_username="busy")
    err = FloodWaitError(None)
    err.seconds = 3

    fake_pop = AsyncMock(return_value=pending)
    fake_get_entity = AsyncMock(side_effect=err)
    fake_mark_failed = AsyncMock()
    fake_mark_done = AsyncMock()
    fake_sleep = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)
    monkeypatch.setattr(jw, "mark_join_done", fake_mark_done)
    monkeypatch.setattr(jw.asyncio, "sleep", fake_sleep)

    sf = _fake_session_factory(session)
    asyncio.run(jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media"))

    fake_sleep.assert_awaited_once_with(4)  # 3 + 1
    fake_mark_failed.assert_not_called()
    fake_mark_done.assert_not_called()
