"""Parse source input from TMA into a typed ParsedSource.

Accepts: @username, bare username, t.me/<name>, t.me/+hash, t.me/joinchat/hash.
Rejects everything else (with leading whitespace stripped before checks).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_PRIVATE = re.compile(r"^(?:https?://)?t\.me/(?:joinchat/|\+)([A-Za-z0-9_-]{1,128})/?$")
_PUBLIC_URL = re.compile(r"^(?:https?://)?t\.me/([A-Za-z0-9_]{5,64})/?$")
_USERNAME = re.compile(r"^@?([A-Za-z0-9_]{5,64})$")


@dataclass(frozen=True)
class ParsedSource:
    kind: Literal["public_username", "private_invite"]
    username: str | None = None
    invite_hash: str | None = None


class ParseError(ValueError):
    """Raised when the input does not match any known source format."""


def parse_source_input(raw: str) -> ParsedSource:
    s = (raw or "").strip()
    if not s or len(s) > 256:
        raise ParseError("invalid_source_input")
    if m := _PRIVATE.match(s):
        return ParsedSource(kind="private_invite", invite_hash=m.group(1))
    if m := _PUBLIC_URL.match(s):
        return ParsedSource(kind="public_username", username=m.group(1).lower())
    if m := _USERNAME.match(s):
        return ParsedSource(kind="public_username", username=m.group(1).lower())
    raise ParseError("invalid_source_input")
