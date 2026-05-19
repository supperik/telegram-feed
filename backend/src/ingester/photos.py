"""Download photos and video thumbnails from Telegram and persist them in
MinIO. Returns the storage_key the caller should record on the media row.

Both helpers are tolerant of missing media: if Telethon's `download_media`
returns None (e.g., FILE_REFERENCE_EXPIRED), we log and return None
without uploading. The caller leaves storage_key=None on the row.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

import structlog
from minio import Minio
from telethon import TelegramClient

log = structlog.get_logger(__name__)


async def download_and_store_photo(
    client: TelegramClient,
    minio_client: Minio,
    msg: Any,
    *,
    channel_id: int,
    bucket: str,
) -> str | None:
    """Download msg.photo and upload to MinIO. Returns the storage key or None."""
    photo = msg.photo
    if photo is None:
        return None
    data = await client.download_media(photo, bytes)
    if not data:
        log.warning("photos.empty_download", channel_id=channel_id, msg_id=msg.id)
        return None

    key = f"photos/{channel_id}/{msg.id}_{photo.id}.jpg"
    minio_client.put_object(
        bucket,
        key,
        BytesIO(data),
        length=len(data),
        content_type="image/jpeg",
    )
    return key


async def download_and_store_video_thumb(
    client: TelegramClient,
    minio_client: Minio,
    msg: Any,
    *,
    channel_id: int,
    bucket: str,
) -> str | None:
    """Download the largest thumbnail of msg.video and upload to MinIO.
    Returns the storage key or None if no thumb is available.

    Pass the parent message + `thumb` index to download_media, not a raw
    thumb object. Raw PhotoStrippedSize / PhotoPathSize entries yield
    empty bytes because they're inline placeholders without
    InputDocumentFileLocation file refs; Telethon resolves the correct
    downloadable thumb when given the message + index.
    """
    video = msg.video
    if video is None:
        return None
    thumbs = getattr(video, "thumbs", None) or []
    if not thumbs:
        return None
    data = await client.download_media(msg, bytes, thumb=-1)
    if not data:
        log.warning("photos.empty_video_thumb", channel_id=channel_id, msg_id=msg.id)
        return None

    key = f"video_thumbs/{channel_id}/{msg.id}_{video.id}.jpg"
    minio_client.put_object(
        bucket,
        key,
        BytesIO(data),
        length=len(data),
        content_type="image/jpeg",
    )
    return key


async def download_and_store_channel_photo(
    client: TelegramClient,
    minio_client: Minio,
    entity: Any,
    *,
    channel_id: int,
    bucket: str,
) -> str | None:
    """Download the profile photo of `entity` (a Telegram channel) and
    upload it to MinIO under a deterministic key. Returns the storage key
    or None if the channel has no avatar / download failed.

    The key is `channel_photos/{channel_id}.jpg` — one slot per channel.
    Re-running overwrites the previous bytes, which is the right behaviour
    when an admin updates the channel's avatar.
    """
    data = await client.download_profile_photo(entity, file=bytes)
    if not data:
        log.warning("photos.no_channel_photo", channel_id=channel_id)
        return None

    key = f"channel_photos/{channel_id}.jpg"
    minio_client.put_object(
        bucket,
        key,
        BytesIO(data),
        length=len(data),
        content_type="image/jpeg",
    )
    return key


async def download_and_store_video(
    client: TelegramClient,
    minio_client: Minio,
    msg: Any,
    *,
    channel_id: int,
    bucket: str,
) -> str | None:
    """Download msg.video and upload to MinIO. Returns the storage key or None.

    Skipped here (returns None) only when the message has no video or the
    download yields empty bytes. Cap-by-size logic lives in
    `_maybe_download_full_video` so callers can decide whether to call this
    at all.
    """
    video = msg.video
    if video is None:
        return None
    data = await client.download_media(msg, bytes)
    if not data:
        log.warning("photos.empty_video", channel_id=channel_id, msg_id=msg.id)
        return None

    key = f"videos/{channel_id}/{msg.id}_{video.id}.mp4"
    minio_client.put_object(
        bucket,
        key,
        BytesIO(data),
        length=len(data),
        content_type="video/mp4",
    )
    return key


async def _maybe_download_full_video(
    client: TelegramClient,
    minio_client: Minio,
    msg: Any,
    *,
    channel_id: int,
    bucket: str,
    settings: Any,
) -> str | None:
    """Download the full video iff size and duration are within the
    configured caps. Returns the storage_key, or None if skipped/failed.

    Cap logic is intentionally additive — failure here MUST NOT undo the
    thumb-download that caller has already performed.
    """
    video = getattr(msg, "video", None)
    if video is None:
        return None
    size = getattr(video, "size", None) or 0
    duration = getattr(video, "duration", None)
    if size > settings.video_max_download_bytes:
        return None
    if duration is not None and duration > settings.video_max_download_seconds:
        return None
    try:
        return await download_and_store_video(
            client, minio_client, msg,
            channel_id=channel_id, bucket=bucket,
        )
    except Exception as e:  # noqa: BLE001 — cap-helper must never raise
        log.warning(
            "photos.full_video_download_failed",
            channel_id=channel_id, msg_id=getattr(msg, "id", None),
            error=str(e),
        )
        return None
