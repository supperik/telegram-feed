"""Tests for ingester.backfill: idempotent re-download of media whose
storage_key=NULL slipped through the catchup gap (telegram-feed-pj0)."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


class _S:
    """Stand-in for shared.config.Settings — only the fields the cap-helper reads."""
    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


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


def _result_one_or_none(value):
    r = MagicMock()
    r.one_or_none = MagicMock(return_value=value)
    return r


def test_backfill_returns_zero_when_no_targets(monkeypatch):
    """If no channel has media with storage_key=NULL, function exits without
    touching Telethon (idempotent no-op for healthy state)."""
    from ingester import backfill

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock()
    fake_client.iter_messages = MagicMock()

    session = MagicMock()
    session.commit = AsyncMock()
    # Single execute call returns empty targets.
    session.execute = AsyncMock(return_value=_result_with_all([]))
    sf = _session_factory(session)

    async def run():
        return await backfill.backfill_recent_media(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=50
        )

    result = asyncio.run(run())

    assert result == 0
    fake_client.get_entity.assert_not_awaited()
    fake_client.iter_messages.assert_not_called()


def test_backfill_downloads_photo_for_existing_post_with_missing_storage_key(monkeypatch):
    """One channel has an old post whose Media row has storage_key=NULL.
    Backfill fetches last N messages, matches by tg_message_id, finds the
    Media row, and delegates to download_and_set_storage_keys with the
    correct shape of media_values."""
    from ingester import backfill

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    async def gen():
        m = MagicMock(id=42)
        m.photo = MagicMock()
        m.video = None
        yield m

    fake_client.iter_messages = MagicMock(return_value=gen())

    # Execute call sequence:
    # 1) targets query — one channel (id=7, tg_chat_id=-100)
    # 2) Post lookup by (channel_id, tg_message_id) — returns (post_id=42,)
    # 3) Media query for that post with storage_key=NULL — returns one row
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(7, -100)]),                       # targets
        _result_one_or_none((42,)),                          # post lookup
        _result_with_all([MagicMock(type="photo", tg_file_id="p1")]),  # media
    ])
    sf = _session_factory(session)

    fake_helper = AsyncMock()
    monkeypatch.setattr(backfill, "download_and_set_storage_keys", fake_helper)

    async def run():
        return await backfill.backfill_recent_media(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=50
        )

    result = asyncio.run(run())

    fake_client.get_entity.assert_awaited_once_with(-100)
    fake_client.iter_messages.assert_called_once()
    fake_helper.assert_awaited_once()
    _, kwargs = fake_helper.call_args
    assert kwargs["channel_id"] == 7
    assert kwargs["new_post_id"] == 42
    assert kwargs["media_values"] == [{"type": "photo", "tg_file_id": "p1"}]
    assert result == 1


def test_backfill_skips_message_without_matching_post_in_db(monkeypatch):
    """If iter_messages yields a Telegram message we don't have in DB
    (e.g., never ingested), backfill silently skips it."""
    from ingester import backfill

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    async def gen():
        m = MagicMock(id=999)
        m.photo = MagicMock()
        m.video = None
        yield m

    fake_client.iter_messages = MagicMock(return_value=gen())

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(7, -100)]),       # targets
        _result_one_or_none(None),           # post not in DB
    ])
    sf = _session_factory(session)

    fake_helper = AsyncMock()
    monkeypatch.setattr(backfill, "download_and_set_storage_keys", fake_helper)

    async def run():
        return await backfill.backfill_recent_media(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=50
        )

    result = asyncio.run(run())

    fake_helper.assert_not_awaited()
    assert result == 0


def test_backfill_skips_messages_without_media(monkeypatch):
    """Text-only messages are skipped quickly without DB queries beyond the
    targets fetch (cheap pass when channel has only text posts since the
    last backfill window)."""
    from ingester import backfill

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    async def gen():
        m = MagicMock(id=1)
        m.photo = None
        m.video = None
        yield m

    fake_client.iter_messages = MagicMock(return_value=gen())

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(7, -100)]),  # targets only — no further calls
    ])
    sf = _session_factory(session)

    fake_helper = AsyncMock()
    monkeypatch.setattr(backfill, "download_and_set_storage_keys", fake_helper)

    async def run():
        return await backfill.backfill_recent_media(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=50
        )

    result = asyncio.run(run())

    fake_helper.assert_not_awaited()
    # exactly 1 execute (targets) — no per-message DB work
    assert session.execute.await_count == 1
    assert result == 0


def test_backfill_continues_when_get_entity_fails(monkeypatch):
    """If get_entity raises (e.g. PeerUser without access_hash), backfill
    logs and moves to the next channel without crashing the boot sequence."""
    from ingester import backfill

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(side_effect=Exception("entity missing"))
    fake_client.iter_messages = MagicMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(7, -100), (8, -200)]),  # two channels, both fail
    ])
    sf = _session_factory(session)

    async def run():
        return await backfill.backfill_recent_media(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=50
        )

    result = asyncio.run(run())

    assert fake_client.get_entity.await_count == 2
    fake_client.iter_messages.assert_not_called()
    assert result == 0
