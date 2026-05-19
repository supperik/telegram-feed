"""Logging masks for secret tokens.

Invite hashes (Telegram private invite links) are secret-ish — they grant
join access to the channel. We don't store them long-term in logs; we
ALWAYS mask them via mask_invite_hash() before passing to structlog.
"""
from __future__ import annotations

__all__ = ["mask_invite_hash"]


def mask_invite_hash(h: str | None) -> str:
    """Return a non-secret representation of an invite hash for logs.

    Examples:
        >>> mask_invite_hash("abcDEF1234567")
        'abcD…67'
        >>> mask_invite_hash(None)
        '***'
        >>> mask_invite_hash("short")
        '***'

    Hashes shorter than 8 characters are entirely masked because the first
    4 + last 2 would reveal too much of a short token.
    """
    if not h or len(h) < 8:
        return "***"
    return f"{h[:4]}…{h[-2:]}"
