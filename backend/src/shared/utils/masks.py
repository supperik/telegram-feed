"""Logging masks for secret tokens."""
from __future__ import annotations


def mask_invite_hash(h: str | None) -> str:
    if not h or len(h) < 8:
        return "***"
    return f"{h[:4]}…{h[-2:]}"
