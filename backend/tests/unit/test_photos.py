import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch


def _fake_msg_with_photo(message_id: int, photo_id: int):
    msg = MagicMock()
    msg.id = message_id
    msg.photo = MagicMock(id=photo_id)
    return msg


def _fake_msg_with_video(message_id: int, video_id: int):
    msg = MagicMock()
    msg.id = message_id
    msg.video = MagicMock(id=video_id)
    msg.video.thumbs = [MagicMock(), MagicMock(), MagicMock()]  # largest is last
    return msg


def test_download_and_store_photo_uses_correct_key_and_uploads():
    from ingester.photos import download_and_store_photo

    fake_client = MagicMock()
    fake_client.download_media = AsyncMock(return_value=b"\x89PNGfakebytes")

    fake_minio = MagicMock()

    msg = _fake_msg_with_photo(message_id=42, photo_id=9001)

    async def run():
        return await download_and_store_photo(
            fake_client, fake_minio, msg, channel_id=7, bucket="media"
        )

    key = asyncio.run(run())

    assert key == "photos/7/42_9001.jpg"
    fake_client.download_media.assert_awaited_once_with(msg.photo, bytes)
    fake_minio.put_object.assert_called_once()
    args, kwargs = fake_minio.put_object.call_args
    # put_object(bucket, key, data, length=..., content_type=...)
    assert args[0] == "media"
    assert args[1] == "photos/7/42_9001.jpg"
    # data is a BytesIO with the bytes
    assert isinstance(args[2], BytesIO)
    assert kwargs.get("length") == len(b"\x89PNGfakebytes")
    assert kwargs.get("content_type") == "image/jpeg"


def test_download_video_thumbnail_uses_largest_thumb():
    from ingester.photos import download_and_store_video_thumb

    fake_client = MagicMock()
    fake_client.download_media = AsyncMock(return_value=b"thumbbytes")
    fake_minio = MagicMock()

    msg = _fake_msg_with_video(message_id=55, video_id=7777)

    async def run():
        return await download_and_store_video_thumb(
            fake_client, fake_minio, msg, channel_id=3, bucket="media"
        )

    key = asyncio.run(run())

    assert key == "video_thumbs/3/55_7777.jpg"
    # Largest thumb is msg.video.thumbs[-1].
    fake_client.download_media.assert_awaited_once_with(msg.video.thumbs[-1], bytes)
    fake_minio.put_object.assert_called_once()
    args, kwargs = fake_minio.put_object.call_args
    assert args[0] == "media"
    assert args[1] == "video_thumbs/3/55_7777.jpg"
    assert kwargs.get("content_type") == "image/jpeg"


def test_download_returns_none_when_telethon_returns_none():
    """If the file is no longer accessible, download_media may return None
    (e.g., FILE_REFERENCE_EXPIRED). We treat that as a soft failure: log,
    return None, don't upload anything."""
    from ingester.photos import download_and_store_photo

    fake_client = MagicMock()
    fake_client.download_media = AsyncMock(return_value=None)
    fake_minio = MagicMock()

    msg = _fake_msg_with_photo(message_id=99, photo_id=1)

    async def run():
        return await download_and_store_photo(
            fake_client, fake_minio, msg, channel_id=1, bucket="media"
        )

    key = asyncio.run(run())
    assert key is None
    fake_minio.put_object.assert_not_called()


def test_download_video_thumb_returns_none_when_no_thumbs():
    from ingester.photos import download_and_store_video_thumb

    fake_client = MagicMock()
    fake_minio = MagicMock()

    msg = MagicMock()
    msg.id = 1
    msg.video = MagicMock(id=1)
    msg.video.thumbs = []

    async def run():
        return await download_and_store_video_thumb(
            fake_client, fake_minio, msg, channel_id=1, bucket="media"
        )

    key = asyncio.run(run())
    assert key is None
    fake_client.download_media.assert_not_called()
    fake_minio.put_object.assert_not_called()
