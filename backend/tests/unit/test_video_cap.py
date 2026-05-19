from unittest.mock import AsyncMock, MagicMock

import pytest


class _S:
    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


def _make_msg(*, size: int | None, duration: int | None):
    msg = MagicMock()
    msg.id = 42
    msg.video = MagicMock()
    msg.video.id = 7
    msg.video.size = size
    msg.video.duration = duration
    return msg


@pytest.mark.asyncio
async def test_skips_when_size_above_cap(monkeypatch):
    from ingester import photos
    called = AsyncMock(return_value="videos/k")
    monkeypatch.setattr(photos, "download_and_store_video", called)
    out = await photos._maybe_download_full_video(
        client=MagicMock(), minio_client=MagicMock(),
        msg=_make_msg(size=21 * 1024 * 1024, duration=30),
        channel_id=1, bucket="media", settings=_S(),
    )
    assert out is None
    called.assert_not_awaited()


@pytest.mark.asyncio
async def test_skips_when_duration_above_cap(monkeypatch):
    from ingester import photos
    called = AsyncMock(return_value="videos/k")
    monkeypatch.setattr(photos, "download_and_store_video", called)
    out = await photos._maybe_download_full_video(
        client=MagicMock(), minio_client=MagicMock(),
        msg=_make_msg(size=1024, duration=61),
        channel_id=1, bucket="media", settings=_S(),
    )
    assert out is None
    called.assert_not_awaited()


@pytest.mark.asyncio
async def test_downloads_when_under_both_caps(monkeypatch):
    from ingester import photos
    called = AsyncMock(return_value="videos/1/42_7.mp4")
    monkeypatch.setattr(photos, "download_and_store_video", called)
    out = await photos._maybe_download_full_video(
        client=MagicMock(), minio_client=MagicMock(),
        msg=_make_msg(size=5 * 1024 * 1024, duration=30),
        channel_id=1, bucket="media", settings=_S(),
    )
    assert out == "videos/1/42_7.mp4"
    called.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_duration_uses_only_size_cap(monkeypatch):
    from ingester import photos
    called = AsyncMock(return_value="videos/k")
    monkeypatch.setattr(photos, "download_and_store_video", called)
    out = await photos._maybe_download_full_video(
        client=MagicMock(), minio_client=MagicMock(),
        msg=_make_msg(size=1024, duration=None),
        channel_id=1, bucket="media", settings=_S(),
    )
    assert out == "videos/k"


@pytest.mark.asyncio
async def test_returns_none_when_no_video():
    from ingester import photos
    msg = MagicMock()
    msg.video = None
    out = await photos._maybe_download_full_video(
        client=MagicMock(), minio_client=MagicMock(),
        msg=msg, channel_id=1, bucket="media", settings=_S(),
    )
    assert out is None


@pytest.mark.asyncio
async def test_swallows_download_exception_and_returns_none(monkeypatch):
    from ingester import photos

    async def boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(photos, "download_and_store_video", boom)

    out = await photos._maybe_download_full_video(
        client=MagicMock(), minio_client=MagicMock(),
        msg=_make_msg(size=1024, duration=10),
        channel_id=1, bucket="media", settings=_S(),
    )
    assert out is None
