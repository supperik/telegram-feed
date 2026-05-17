from datetime import datetime, timezone

import pytest

from api.errors import APIError
from api.pagination import FeedCursor


def test_cursor_roundtrip() -> None:
    c = FeedCursor(posted_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc), post_id=42)
    s = c.encode()
    back = FeedCursor.decode(s)
    assert back == c


def test_cursor_decode_rejects_garbage() -> None:
    with pytest.raises(APIError) as excinfo:
        FeedCursor.decode("@@@not-base64@@@")
    assert excinfo.value.code == "bad_cursor"


def test_cursor_initial_sentinel() -> None:
    c = FeedCursor.initial()
    # Sentinel sorts strictly after any real post.
    assert c.post_id == 0
    assert c.posted_at.year >= 9999 or c.posted_at > datetime.now(tz=timezone.utc)
