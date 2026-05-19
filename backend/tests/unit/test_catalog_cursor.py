from datetime import datetime, timezone

import pytest

from api.errors import APIError
from api.pagination import CatalogCursor


def test_catalog_cursor_available_initial_is_max_popularity() -> None:
    c = CatalogCursor.initial_available()
    # initial cursor must compare greater than any real row in keyset DESC
    assert c.posts_count > 1_000_000_000
    assert c.channel_id == 0


def test_catalog_cursor_hidden_initial_is_max_time() -> None:
    c = CatalogCursor.initial_hidden()
    assert c.hidden_at.year == 9999
    assert c.channel_id == 0


def test_catalog_cursor_available_roundtrip() -> None:
    c = CatalogCursor.available(posts_count=42, channel_id=7)
    s = c.encode()
    assert "available" in CatalogCursor.decode(s).view
    decoded = CatalogCursor.decode(s)
    assert decoded.posts_count == 42
    assert decoded.channel_id == 7
    assert decoded.view == "available"


def test_catalog_cursor_hidden_roundtrip() -> None:
    moment = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    c = CatalogCursor.hidden(hidden_at=moment, channel_id=5)
    decoded = CatalogCursor.decode(c.encode())
    assert decoded.hidden_at == moment
    assert decoded.channel_id == 5
    assert decoded.view == "hidden"


def test_catalog_cursor_bad_string_raises_api_error() -> None:
    with pytest.raises(APIError) as exc:
        CatalogCursor.decode("not-a-cursor")
    assert exc.value.code == "bad_cursor"
