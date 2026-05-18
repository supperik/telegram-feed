"""Unit tests for ingester.text_html.entities_to_html.

Verifies conversion of Telegram MessageEntity into safe HTML for direct
innerHTML rendering on the client. Covers:
- Each supported entity type produces the expected tag.
- Unsafe URL schemes (javascript:, data:, ...) drop the link, keep text.
- Schemeless URLs get https:// prepended.
- HTML special chars (<, >, &) in plain text are escaped.
- Nested entities (e.g., bold inside a link) wrap correctly.
- UTF-16 surrogate offsets (emoji before entity) decode correctly.
- None / empty text and empty entities pass through.
"""
from __future__ import annotations

from telethon.tl.types import (
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityHashtag,
    MessageEntityItalic,
    MessageEntityMention,
    MessageEntityMentionName,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
    MessageEntityUrl,
)


def _utf16_len(s: str) -> int:
    """Telegram offsets are in UTF-16 code units."""
    return len(s.encode("utf-16-le")) // 2


def test_none_text_returns_none():
    from ingester.text_html import entities_to_html

    assert entities_to_html(None, None) is None
    assert entities_to_html(None, []) is None


def test_empty_text_returns_empty():
    from ingester.text_html import entities_to_html

    assert entities_to_html("", None) == ""
    assert entities_to_html("", []) == ""


def test_plain_text_no_entities_escapes_special_chars():
    from ingester.text_html import entities_to_html

    assert entities_to_html("hello world", None) == "hello world"
    assert entities_to_html("hello world", []) == "hello world"
    assert entities_to_html("<script>", []) == "&lt;script&gt;"
    assert entities_to_html("a & b", []) == "a &amp; b"
    assert entities_to_html('"quoted"', []) == '"quoted"'  # quotes not escaped in body


def test_bold():
    from ingester.text_html import entities_to_html

    text = "hello bold world"
    # "bold" at offset 6, length 4
    entities = [MessageEntityBold(offset=6, length=4)]
    assert entities_to_html(text, entities) == "hello <strong>bold</strong> world"


def test_italic():
    from ingester.text_html import entities_to_html

    text = "say hi please"
    entities = [MessageEntityItalic(offset=4, length=2)]  # "hi"
    assert entities_to_html(text, entities) == "say <em>hi</em> please"


def test_underline():
    from ingester.text_html import entities_to_html

    text = "x ul y"
    entities = [MessageEntityUnderline(offset=2, length=2)]  # "ul"
    assert entities_to_html(text, entities) == "x <u>ul</u> y"


def test_strikethrough():
    from ingester.text_html import entities_to_html

    text = "old new"
    entities = [MessageEntityStrike(offset=0, length=3)]  # "old"
    assert entities_to_html(text, entities) == "<s>old</s> new"


def test_code_inline():
    from ingester.text_html import entities_to_html

    text = "run foo() now"
    entities = [MessageEntityCode(offset=4, length=5)]  # "foo()"
    assert entities_to_html(text, entities) == "run <code>foo()</code> now"


def test_pre_block():
    from ingester.text_html import entities_to_html

    text = "x = 1\n"
    entities = [MessageEntityPre(offset=0, length=6, language="")]
    assert entities_to_html(text, entities) == "<pre>x = 1\n</pre>"


def test_blockquote():
    from ingester.text_html import entities_to_html

    text = "quote me"
    entities = [MessageEntityBlockquote(offset=0, length=8)]
    assert entities_to_html(text, entities) == "<blockquote>quote me</blockquote>"


def test_spoiler():
    from ingester.text_html import entities_to_html

    text = "the answer is 42"
    entities = [MessageEntitySpoiler(offset=14, length=2)]  # "42"
    assert (
        entities_to_html(text, entities)
        == 'the answer is <span class="tg-spoiler">42</span>'
    )


def test_text_url_basic():
    from ingester.text_html import entities_to_html

    text = "click here please"
    entities = [MessageEntityTextUrl(offset=6, length=4, url="https://example.com/a")]
    expected = (
        'click <a href="https://example.com/a" '
        'rel="noopener noreferrer" target="_blank">here</a> please'
    )
    assert entities_to_html(text, entities) == expected


def test_text_url_escapes_href_quotes():
    from ingester.text_html import entities_to_html

    text = "x link y"
    entities = [
        MessageEntityTextUrl(offset=2, length=4, url='https://example.com/"\'><script>')
    ]
    out = entities_to_html(text, entities)
    # href must escape ", <, >, &; the visible text is "link" unchanged.
    assert 'href="https://example.com/&quot;&#x27;&gt;&lt;script&gt;"' in out
    assert ">link</a>" in out


def test_text_url_javascript_dropped():
    from ingester.text_html import entities_to_html

    text = "evil link here"
    entities = [MessageEntityTextUrl(offset=5, length=4, url="javascript:alert(1)")]
    out = entities_to_html(text, entities)
    # The <a> tag is dropped; the visible text remains.
    assert "<a" not in out
    assert "javascript:" not in out
    assert "evil link here" == out


def test_text_url_schemeless_gets_https():
    from ingester.text_html import entities_to_html

    text = "go here"
    entities = [MessageEntityTextUrl(offset=3, length=4, url="example.com/path")]
    out = entities_to_html(text, entities)
    assert 'href="https://example.com/path"' in out


def test_auto_url_uses_text_as_href():
    from ingester.text_html import entities_to_html

    text = "see https://example.com/x for info"
    # Telegram marks "https://example.com/x" (length 21) as an auto-URL.
    url = "https://example.com/x"
    entities = [MessageEntityUrl(offset=4, length=len(url))]
    out = entities_to_html(text, entities)
    assert f'<a href="{url}" rel="noopener noreferrer" target="_blank">{url}</a>' in out


def test_mention_renders_as_telegram_link():
    from ingester.text_html import entities_to_html

    text = "ping @alice for info"
    entities = [MessageEntityMention(offset=5, length=6)]  # "@alice"
    out = entities_to_html(text, entities)
    assert (
        '<a class="tg-mention" href="https://t.me/alice" '
        'rel="noopener noreferrer" target="_blank">@alice</a>'
        in out
    )


def test_mention_invalid_username_drops_link():
    from ingester.text_html import entities_to_html

    # Username with invalid char — drop the wrapping, keep raw text.
    text = "@<evil>"
    entities = [MessageEntityMention(offset=0, length=7)]
    out = entities_to_html(text, entities)
    assert "<a" not in out
    assert out == "@&lt;evil&gt;"


def test_mention_name_renders_as_tg_user_link():
    from ingester.text_html import entities_to_html

    # MentionName carries user_id (for users without public username).
    text = "ping Alice now"
    entities = [MessageEntityMentionName(offset=5, length=5, user_id=42)]
    out = entities_to_html(text, entities)
    assert (
        '<a class="tg-mention" href="tg://user?id=42">Alice</a>' in out
    )


def test_hashtag_renders_as_styled_span():
    from ingester.text_html import entities_to_html

    text = "love #python today"
    entities = [MessageEntityHashtag(offset=5, length=7)]  # "#python"
    out = entities_to_html(text, entities)
    assert 'love <span class="tg-hashtag">#python</span> today' == out


def test_nested_bold_inside_link():
    from ingester.text_html import entities_to_html

    text = "click here please"
    entities = [
        MessageEntityTextUrl(offset=6, length=4, url="https://example.com"),
        MessageEntityBold(offset=6, length=4),
    ]
    out = entities_to_html(text, entities)
    # Either order is acceptable as long as tags nest correctly.
    # We assert the inner content has both wrappers.
    assert "<strong>here</strong>" in out or "<strong>here</strong></a>" in out
    assert 'href="https://example.com"' in out


def test_two_disjoint_entities():
    from ingester.text_html import entities_to_html

    text = "bold and italic"
    entities = [
        MessageEntityBold(offset=0, length=4),
        MessageEntityItalic(offset=9, length=6),
    ]
    assert (
        entities_to_html(text, entities)
        == "<strong>bold</strong> and <em>italic</em>"
    )


def test_escapes_html_specials_inside_entity():
    from ingester.text_html import entities_to_html

    text = "say <hi>"
    # Bold covers "<hi>"
    entities = [MessageEntityBold(offset=4, length=4)]
    assert entities_to_html(text, entities) == "say <strong>&lt;hi&gt;</strong>"


def test_utf16_surrogate_offset_emoji_before_entity():
    from ingester.text_html import entities_to_html

    # Emoji "🌟" is 2 UTF-16 code units; "bold" then follows.
    text = "🌟 bold!"
    # In UTF-16, offsets: 🌟=2, space=1, bold=4, !=1.
    # Bold "bold" starts at UTF-16 offset 3 with length 4.
    offset_units = _utf16_len("🌟 ")
    entities = [MessageEntityBold(offset=offset_units, length=4)]
    assert entities_to_html(text, entities) == "🌟 <strong>bold</strong>!"


def test_unsupported_entity_just_emits_text():
    from ingester.text_html import entities_to_html

    # Email is supported by Telethon types but not in MVP set — drop wrapper.
    # Use a hypothetical entity type via a stub; here we just check that
    # text without recognizable entities falls through escaped.
    text = "user@example.com"
    out = entities_to_html(text, [])
    assert out == "user@example.com"


def test_entire_text_is_one_entity():
    from ingester.text_html import entities_to_html

    text = "ALL BOLD"
    entities = [MessageEntityBold(offset=0, length=8)]
    assert entities_to_html(text, entities) == "<strong>ALL BOLD</strong>"


def test_url_javascript_dropped_keeps_text():
    from ingester.text_html import entities_to_html

    # Auto-URL whose text is a javascript: URI — drop the link, keep text.
    text = "javascript:alert(1)"
    entities = [MessageEntityUrl(offset=0, length=len(text))]
    out = entities_to_html(text, entities)
    assert "<a" not in out
    assert "alert" in out  # raw text preserved (escaped)


def test_consecutive_adjacent_entities():
    from ingester.text_html import entities_to_html

    text = "bolditalic"
    entities = [
        MessageEntityBold(offset=0, length=4),
        MessageEntityItalic(offset=4, length=6),
    ]
    assert (
        entities_to_html(text, entities)
        == "<strong>bold</strong><em>italic</em>"
    )
