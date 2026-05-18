"""Pure mapping from Telethon Message objects to (post_dict, media_dicts).

No I/O, no DB, no media download. The result feeds straight into
SQLAlchemy inserts:
    session.execute(insert(Post).values(**post_dict))
    for md in media_dicts: session.execute(insert(Media).values(**md))

`storage_key` is left None in media dicts — Phase 3 (photos.py)
fills it in after the actual download.

For Telegram media groups (`msg.grouped_id`), use `normalize_album`
instead — it folds N messages into a single Post with N Media rows.
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


def _media_dict_for_msg(msg: Any, position: int) -> dict | None:
    """Return a Media row dict for the single media unit on `msg`, or
    None if the message has no media."""
    photo = getattr(msg, "photo", None)
    video = getattr(msg, "video", None)
    document = getattr(msg, "document", None)

    if photo is not None:
        w, h = _largest_photo_size(photo)
        return {
            "type": "photo",
            "storage_key": None,
            "tg_file_id": str(photo.id),
            "width": w,
            "height": h,
            "duration": None,
            "size_bytes": None,
            "position": position,
        }
    if video is not None:
        f = getattr(msg, "file", None)
        return {
            "type": "video",
            "storage_key": None,
            "tg_file_id": str(video.id),
            "width": getattr(f, "width", None) if f else None,
            "height": getattr(f, "height", None) if f else None,
            "duration": getattr(video, "duration", None),
            "size_bytes": getattr(video, "size", None),
            "position": position,
        }
    if document is not None:
        return {
            "type": "document",
            "storage_key": None,
            "tg_file_id": str(document.id),
            "width": None,
            "height": None,
            "duration": None,
            "size_bytes": getattr(document, "size", None),
            "position": position,
        }
    return None


def normalize_message(msg: Any, channel_id: int) -> tuple[dict, list[dict]]:
    text = getattr(msg, "message", None) or getattr(msg, "text", None)
    entities = getattr(msg, "entities", None)
    post = {
        "channel_id": channel_id,
        "tg_message_id": int(msg.id),
        "tg_grouped_id": getattr(msg, "grouped_id", None),
        "text": text,
        "text_html": entities_to_html(text, entities),
        "posted_at": msg.date,
        "edited_at": getattr(msg, "edit_date", None),
        "views": getattr(msg, "views", None),
        "forwards": getattr(msg, "forwards", None),
    }

    media: list[dict] = []
    m = _media_dict_for_msg(msg, position=0)
    if m is not None:
        media.append(m)

    return post, media


def normalize_album(messages: list[Any], channel_id: int) -> tuple[dict, list[dict]]:
    """Fold a list of messages that share a `grouped_id` into a single
    Post (with min `msg.id` as `tg_message_id`) and N Media rows ordered
    by `msg.id`.

    Caption is taken from the first message in id-order whose `.message`
    is non-empty; its `entities` are used for text_html as well. The
    head message's metadata (date / views / forwards) is used for the
    Post.
    """
    if not messages:
        raise ValueError("normalize_album requires at least one message")

    ordered = sorted(messages, key=lambda m: int(m.id))
    head = ordered[0]

    caption_msg = next(
        (m for m in ordered if (getattr(m, "message", None) or getattr(m, "text", None))),
        None,
    )
    if caption_msg is not None:
        text = getattr(caption_msg, "message", None) or getattr(caption_msg, "text", None)
        entities = getattr(caption_msg, "entities", None)
    else:
        text = None
        entities = None

    post = {
        "channel_id": channel_id,
        "tg_message_id": int(head.id),
        "tg_grouped_id": getattr(head, "grouped_id", None),
        "text": text,
        "text_html": entities_to_html(text, entities),
        "posted_at": head.date,
        "edited_at": getattr(head, "edit_date", None),
        "views": getattr(head, "views", None),
        "forwards": getattr(head, "forwards", None),
    }

    media: list[dict] = []
    for idx, msg in enumerate(ordered):
        m = _media_dict_for_msg(msg, position=idx)
        if m is not None:
            media.append(m)

    return post, media
