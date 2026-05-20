from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from api.errors import APIError


@dataclass(frozen=True)
class FeedCursor:
    posted_at: datetime
    post_id: int

    def encode(self) -> str:
        raw = f"{self.posted_at.isoformat()}|{self.post_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, s: str) -> FeedCursor:
        try:
            padded = s + "=" * (-len(s) % 4)
            raw = base64.urlsafe_b64decode(padded.encode()).decode()
            posted, pid = raw.split("|", 1)
            return cls(posted_at=datetime.fromisoformat(posted), post_id=int(pid))
        except Exception as e:  # noqa: BLE001
            raise APIError(code="bad_cursor", message="Cursor is malformed", status_code=400) from e

    @classmethod
    def initial(cls) -> FeedCursor:
        # Far future + post_id=0 so the keyset predicate `(posted_at, id) < cursor`
        # returns the latest post first.
        return cls(posted_at=datetime(9999, 12, 31, tzinfo=UTC), post_id=0)


@dataclass(frozen=True)
class PostListCursor:
    """Keyset cursor for /posts/saved, /posts/hidden and /posts/read.

    Sort key is `(sort_at, post_id)` where sort_at is the saved_at,
    hidden_at or read_at timestamp depending on the endpoint. Same encoding
    shape for all — the endpoint knows which it asked for.
    """
    sort_at: datetime
    post_id: int

    def encode(self) -> str:
        raw = f"{self.sort_at.isoformat()}|{self.post_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, s: str) -> PostListCursor:
        try:
            padded = s + "=" * (-len(s) % 4)
            raw = base64.urlsafe_b64decode(padded.encode()).decode()
            sort_at, pid = raw.split("|", 1)
            return cls(sort_at=datetime.fromisoformat(sort_at), post_id=int(pid))
        except Exception as e:  # noqa: BLE001
            raise APIError(
                code="bad_cursor", message="Cursor is malformed", status_code=400
            ) from e

    @classmethod
    def initial(cls) -> PostListCursor:
        return cls(sort_at=datetime(9999, 12, 31, tzinfo=UTC), post_id=0)


@dataclass(frozen=True)
class CatalogCursor:
    """Keyset cursor for /channels/catalog.

    Two shapes share one class so the encoded string self-identifies the
    view (and the API can't pass an `available` cursor into a `hidden`
    request).
    """
    view: Literal["available", "hidden"]
    posts_count: int          # used when view == "available"
    hidden_at: datetime       # used when view == "hidden"
    channel_id: int

    @classmethod
    def available(cls, *, posts_count: int, channel_id: int) -> CatalogCursor:
        return cls(
            view="available",
            posts_count=posts_count,
            hidden_at=datetime(1970, 1, 1, tzinfo=UTC),
            channel_id=channel_id,
        )

    @classmethod
    def hidden(cls, *, hidden_at: datetime, channel_id: int) -> CatalogCursor:
        return cls(
            view="hidden",
            posts_count=0,
            hidden_at=hidden_at,
            channel_id=channel_id,
        )

    @classmethod
    def initial_available(cls) -> CatalogCursor:
        # posts_count > any real value; channel_id=0 so the keyset
        # predicate (posts_count, channel_id) < cursor matches every row.
        return cls.available(posts_count=2_000_000_000, channel_id=0)

    @classmethod
    def initial_hidden(cls) -> CatalogCursor:
        return cls.hidden(
            hidden_at=datetime(9999, 12, 31, tzinfo=UTC),
            channel_id=0,
        )

    def encode(self) -> str:
        if self.view == "available":
            raw = f"a|{self.posts_count}|{self.channel_id}".encode()
        else:
            raw = f"h|{self.hidden_at.isoformat()}|{self.channel_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, s: str) -> CatalogCursor:
        try:
            padded = s + "=" * (-len(s) % 4)
            raw = base64.urlsafe_b64decode(padded.encode()).decode()
            tag, rest = raw.split("|", 1)
            if tag == "a":
                pc, cid = rest.split("|", 1)
                return cls.available(posts_count=int(pc), channel_id=int(cid))
            if tag == "h":
                hat, cid = rest.split("|", 1)
                return cls.hidden(
                    hidden_at=datetime.fromisoformat(hat),
                    channel_id=int(cid),
                )
            raise ValueError("unknown cursor tag")
        except Exception as e:  # noqa: BLE001
            raise APIError(
                code="bad_cursor", message="Cursor is malformed", status_code=400
            ) from e
