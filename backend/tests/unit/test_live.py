"""Tests for the video-cap wire-in inside ingester.live.

Task 7 of the private-channel-ux-and-short-video epic added a call to
`_maybe_download_full_video` next to the existing thumb download in every
mtype=="video" branch. When the helper returns a key, callers must issue a
second `UPDATE media SET video_storage_key=...` alongside the existing
storage_key update.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest


class _S:
    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


@pytest.mark.asyncio
async def test_download_and_set_storage_keys_updates_video_storage_key(monkeypatch):
    """Video media with size and duration under cap should trigger
    two UPDATE statements: one for storage_key (thumb), one for
    video_storage_key (full file)."""
    from ingester import live

    monkeypatch.setattr(
        live, "download_and_store_video_thumb",
        AsyncMock(return_value="video_thumbs/1/42_7.jpg"),
    )
    monkeypatch.setattr(
        live, "_maybe_download_full_video",
        AsyncMock(return_value="videos/1/42_7.mp4"),
    )

    session = MagicMock()
    session.execute = AsyncMock()
    msg = MagicMock()
    msg.id = 42

    media_values = [{
        "type": "video",
        "tg_file_id": "7",
    }]

    await live.download_and_set_storage_keys(
        session,
        msg=msg,
        channel_id=1,
        new_post_id=99,
        media_values=media_values,
        client=MagicMock(),
        minio_client=MagicMock(),
        bucket="media",
        settings=_S(),
    )

    update_calls = session.execute.await_args_list
    keys_set = []
    for call in update_calls:
        stmt = call.args[0]
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)
        keys_set.append(compiled)
    assert any("storage_key" in c and "video_storage_key" not in c for c in keys_set), keys_set
    assert any("video_storage_key" in c for c in keys_set), keys_set


@pytest.mark.asyncio
async def test_download_and_set_storage_keys_does_not_update_video_key_when_skipped(monkeypatch):
    """Cap-skip path: _maybe_download_full_video returns None ⇒
    no video_storage_key UPDATE."""
    from ingester import live

    monkeypatch.setattr(
        live, "download_and_store_video_thumb",
        AsyncMock(return_value="video_thumbs/1/42_7.jpg"),
    )
    monkeypatch.setattr(
        live, "_maybe_download_full_video",
        AsyncMock(return_value=None),
    )

    session = MagicMock()
    session.execute = AsyncMock()
    msg = MagicMock()
    msg.id = 42

    await live.download_and_set_storage_keys(
        session,
        msg=msg,
        channel_id=1,
        new_post_id=99,
        media_values=[{"type": "video", "tg_file_id": "7"}],
        client=MagicMock(),
        minio_client=MagicMock(),
        bucket="media",
        settings=_S(),
    )

    for call in session.execute.await_args_list:
        stmt = call.args[0]
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)
        assert "video_storage_key" not in compiled, compiled
