from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone

from api.errors import APIError


@dataclass(frozen=True)
class FeedCursor:
    posted_at: datetime
    post_id: int

    def encode(self) -> str:
        raw = f"{self.posted_at.isoformat()}|{self.post_id}".encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, s: str) -> "FeedCursor":
        try:
            padded = s + "=" * (-len(s) % 4)
            raw = base64.urlsafe_b64decode(padded.encode()).decode()
            posted, pid = raw.split("|", 1)
            return cls(posted_at=datetime.fromisoformat(posted), post_id=int(pid))
        except Exception as e:  # noqa: BLE001
            raise APIError(code="bad_cursor", message="Cursor is malformed", status_code=400) from e

    @classmethod
    def initial(cls) -> "FeedCursor":
        # Far future + post_id=0 so the keyset predicate `(posted_at, id) < cursor`
        # returns the latest post first.
        return cls(posted_at=datetime(9999, 12, 31, tzinfo=timezone.utc), post_id=0)
