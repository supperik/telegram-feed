"""Pure mapping from a Telethon Message to (post_dict, media_dicts).

No I/O, no DB, no media download. The result feeds straight into
SQLAlchemy inserts:
    session.execute(insert(Post).values(**post_dict))
    for md in media_dicts: session.execute(insert(Media).values(**md))

`storage_key` is left None in media dicts — Phase 3 (photos.py)
fills it in after the actual download.
"""
from __future__ import annotations

from typing import Any

from ingester.text_html import entities_to_html


def _largest_photo_size(photo: Any) -> tuple[int | None, int | None]:
    sizes = getattr(photo, "sizes", None) or []
    if not sizes:
        return None, None
    # Pick the size with the largest w*h (some sizes lack w/h — skip those).
    best = None
    for s in sizes:
        w = getattr(s, "w", None)
        h = getattr(s, "h", None)
        if w is None or h is None:
            continue
        area = w * h
        if best is None or area > best[2]:
            best = (w, h, area)
    if best is None:
        return None, None
    return best[0], best[1]


def normalize_message(msg: Any, channel_id: int) -> tuple[dict, list[dict]]:
    text = getattr(msg, "message", None) or getattr(msg, "text", None)
    entities = getattr(msg, "entities", None)
    post = {
        "channel_id": channel_id,
        "tg_message_id": int(msg.id),
        "text": text,
        "text_html": entities_to_html(text, entities),
        "posted_at": msg.date,
        "edited_at": getattr(msg, "edit_date", None),
        "views": getattr(msg, "views", None),
        "forwards": getattr(msg, "forwards", None),
    }

    media: list[dict] = []
    photo = getattr(msg, "photo", None)
    video = getattr(msg, "video", None)
    document = getattr(msg, "document", None)

    if photo is not None:
        w, h = _largest_photo_size(photo)
        media.append(
            {
                "type": "photo",
                "storage_key": None,
                "tg_file_id": str(photo.id),
                "width": w,
                "height": h,
                "duration": None,
                "size_bytes": None,
                "position": 0,
            }
        )
    elif video is not None:
        f = getattr(msg, "file", None)
        media.append(
            {
                "type": "video",
                "storage_key": None,
                "tg_file_id": str(video.id),
                "width": getattr(f, "width", None) if f else None,
                "height": getattr(f, "height", None) if f else None,
                "duration": getattr(video, "duration", None),
                "size_bytes": getattr(video, "size", None),
                "position": 0,
            }
        )
    elif document is not None:
        media.append(
            {
                "type": "document",
                "storage_key": None,
                "tg_file_id": str(document.id),
                "width": None,
                "height": None,
                "duration": None,
                "size_bytes": getattr(document, "size", None),
                "position": 0,
            }
        )

    return post, media
