"""Unit tests for ingester.backfill_channel_photos: one-shot pass that
fills Channel.photo_storage_key for channels still missing an avatar."""
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


def test_backfill_no_targets_returns_zero():
    from ingester import backfill_channel_photos as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock()
    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([]))
    sf = _session_factory(session)
    fake_download = AsyncMock()

    n = asyncio.run(mod.backfill_channel_photos(fake_client, sf, MagicMock(),
                                                  bucket="media",
                                                  downloader=fake_download))

    assert n == 0
    fake_client.get_entity.assert_not_awaited()
    fake_download.assert_not_awaited()


def test_backfill_downloads_and_updates_channel():
    from ingester import backfill_channel_photos as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_download = AsyncMock(return_value="channel_photos/7.jpg")

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(7, -100)]),  # targets
        MagicMock(),                    # UPDATE Channel
    ])
    sf = _session_factory(session)

    n = asyncio.run(mod.backfill_channel_photos(fake_client, sf, MagicMock(),
                                                  bucket="media",
                                                  downloader=fake_download))

    assert n == 1
    fake_client.get_entity.assert_awaited_once_with(-100)
    fake_download.assert_awaited_once()
    _, kwargs = fake_download.call_args
    assert kwargs.get("channel_id") == 7
    update_calls = [
        c for c in session.execute.await_args_list
        if "UPDATE channels" in str(c.args[0])
    ]
    assert update_calls


def test_backfill_skips_channel_when_no_avatar():
    from ingester import backfill_channel_photos as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_download = AsyncMock(return_value=None)  # channel has no avatar

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([(7, -100)]))
    sf = _session_factory(session)

    n = asyncio.run(mod.backfill_channel_photos(fake_client, sf, MagicMock(),
                                                  bucket="media",
                                                  downloader=fake_download))

    assert n == 0
    fake_download.assert_awaited_once()
    # No UPDATE issued.
    assert session.execute.await_count == 1


def test_backfill_continues_when_get_entity_fails():
    from ingester import backfill_channel_photos as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(side_effect=Exception("no entity"))
    fake_download = AsyncMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(return_value=_result_with_all([
        (7, -100), (8, -200),
    ]))
    sf = _session_factory(session)

    n = asyncio.run(mod.backfill_channel_photos(fake_client, sf, MagicMock(),
                                                  bucket="media",
                                                  downloader=fake_download))

    assert n == 0
    assert fake_client.get_entity.await_count == 2
    fake_download.assert_not_awaited()


def test_backfill_continues_when_download_raises():
    from ingester import backfill_channel_photos as mod

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_download = AsyncMock(side_effect=[Exception("flake"), "channel_photos/8.jpg"])

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _result_with_all([(7, -100), (8, -200)]),
        MagicMock(),  # UPDATE channel 8
    ])
    sf = _session_factory(session)

    n = asyncio.run(mod.backfill_channel_photos(fake_client, sf, MagicMock(),
                                                  bucket="media",
                                                  downloader=fake_download))

    assert n == 1
    assert fake_download.await_count == 2
