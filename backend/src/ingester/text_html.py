"""Convert a Telegram message text + entities into safe HTML.

Telegram messages carry a plain `text` string and a list of MessageEntity
objects with UTF-16 code-unit offsets into that text. `entities_to_html`
folds those entities back into an HTML string that can be rendered
directly via innerHTML on a client.

Output is restricted to a small white-list of tags:
    <strong> <em> <u> <s> <code> <pre> <blockquote>
    <span class="tg-spoiler">
    <span class="tg-hashtag">
    <a href="...">                    (plain hyperlink, target=_blank)
    <a class="tg-mention" href="...">

Unrecognized entity types are dropped silently (the underlying text is
still emitted, escaped). URLs are sanitized: only http/https/tg/mailto
are kept; schemeless URLs are upgraded to https://; everything else
(javascript:, data:, etc.) drops the `<a>` wrapper and keeps the raw
text.
"""
from __future__ import annotations

import html as _html
from typing import Any

_ALLOWED_SCHEMES = ("http://", "https://", "tg://", "mailto:")
_BLOCKED_SCHEMES = ("javascript:", "data:", "vbscript:", "file:", "blob:")


def entities_to_html(text: str | None, entities: list[Any] | None) -> str | None:
    """Render `text` annotated with Telegram `entities` as safe HTML.

    Returns None when the input text is None (mirrors Post.text_html
    nullability). Empty string in, empty string out.
    """
    if text is None:
        return None
    if not text:
        return ""
    if not entities:
        return _escape(text)

    converted: list[tuple[int, int, str, str]] = []
    for e in entities:
        char_start = _utf16_to_char(text, int(getattr(e, "offset", 0)))
        char_end = _utf16_to_char(
            text, int(getattr(e, "offset", 0)) + int(getattr(e, "length", 0))
        )
        if char_start >= char_end:
            continue
        if char_start < 0 or char_end > len(text):
            continue
        slice_text = text[char_start:char_end]
        open_tag, close_tag = _tags_for_entity(e, slice_text)
        if open_tag is None or close_tag is None:
            continue
        converted.append((char_start, char_end, open_tag, close_tag))

    if not converted:
        return _escape(text)

    # Open longer entities first at the same start, so they wrap shorter ones.
    converted.sort(key=lambda t: (t[0], -(t[1] - t[0])))

    n = len(text)
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    idx = 0

    for pos in range(n + 1):
        while stack and stack[-1][0] == pos:
            _, close_tag = stack.pop()
            out.append(close_tag)
        while idx < len(converted) and converted[idx][0] == pos:
            _, end, open_tag, close_tag = converted[idx]
            out.append(open_tag)
            stack.append((end, close_tag))
            idx += 1
        if pos < n:
            out.append(_escape_char(text[pos]))

    return "".join(out)


def _utf16_to_char(text: str, utf16_offset: int) -> int:
    """Telegram offsets are UTF-16 code units; convert to Python char index."""
    if utf16_offset <= 0:
        return 0
    utf16 = text.encode("utf-16-le")
    byte_offset = utf16_offset * 2
    if byte_offset >= len(utf16):
        return len(text)
    return len(utf16[:byte_offset].decode("utf-16-le", errors="replace"))


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_char(c: str) -> str:
    if c == "&":
        return "&amp;"
    if c == "<":
        return "&lt;"
    if c == ">":
        return "&gt;"
    return c


def _tags_for_entity(e: Any, slice_text: str) -> tuple[str | None, str | None]:
    name = type(e).__name__

    if name == "MessageEntityBold":
        return "<strong>", "</strong>"
    if name == "MessageEntityItalic":
        return "<em>", "</em>"
    if name == "MessageEntityUnderline":
        return "<u>", "</u>"
    if name in ("MessageEntityStrike", "MessageEntityStrikethrough"):
        return "<s>", "</s>"
    if name == "MessageEntityCode":
        return "<code>", "</code>"
    if name == "MessageEntityPre":
        return "<pre>", "</pre>"
    if name == "MessageEntityBlockquote":
        return "<blockquote>", "</blockquote>"
    if name == "MessageEntitySpoiler":
        return '<span class="tg-spoiler">', "</span>"
    if name == "MessageEntityHashtag":
        return '<span class="tg-hashtag">', "</span>"

    if name == "MessageEntityTextUrl":
        href = _sanitize_href(getattr(e, "url", ""))
        if href is None:
            return None, None
        return _open_anchor(href), "</a>"

    if name == "MessageEntityUrl":
        href = _sanitize_href(slice_text)
        if href is None:
            return None, None
        return _open_anchor(href), "</a>"

    if name == "MessageEntityMention":
        username = slice_text.lstrip("@")
        if not _is_valid_username(username):
            return None, None
        return (
            f'<a class="tg-mention" href="https://t.me/{username}" '
            f'rel="noopener noreferrer" target="_blank">'
        ), "</a>"

    if name == "MessageEntityMentionName":
        user_id = getattr(e, "user_id", None)
        if not isinstance(user_id, int) or user_id <= 0:
            return None, None
        return f'<a class="tg-mention" href="tg://user?id={user_id}">', "</a>"

    return None, None


def _open_anchor(href: str) -> str:
    return f'<a href="{_escape_attr(href)}" rel="noopener noreferrer" target="_blank">'


def _escape_attr(s: str) -> str:
    return _html.escape(s, quote=True)


def _sanitize_href(url: str) -> str | None:
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    lower = candidate.lower()
    for blocked in _BLOCKED_SCHEMES:
        if lower.startswith(blocked):
            return None
    for allowed in _ALLOWED_SCHEMES:
        if lower.startswith(allowed):
            return candidate
    if "://" in candidate or candidate.startswith("//"):
        # Unknown explicit scheme — refuse rather than trust it.
        return None
    return f"https://{candidate}"


def _is_valid_username(s: str) -> bool:
    if not s or len(s) > 64:
        return False
    return all(c.isalnum() or c == "_" for c in s)
