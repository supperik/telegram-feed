"""Build a stable URL for a channel's avatar.

When a Channel has a non-null `photo_storage_key`, the canonical URL
to its avatar is `/api/channels/{channel_id}/photo` — served by the
streaming endpoint in `api.routers.channels` with JWT auth (matches
the contract of `/api/media/{id}`).

Centralising the URL shape keeps response builders consistent and makes
future scheme changes (e.g. signed-url tokens, CDN prefixes) a single
edit.
"""
from __future__ import annotations


def channel_photo_url(channel_id: int, storage_key: str | None) -> str | None:
    """Return the public-facing avatar URL, or None if no photo is stored."""
    if not storage_key:
        return None
    return f"/api/channels/{channel_id}/photo"
