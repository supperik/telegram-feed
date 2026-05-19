from __future__ import annotations

import pytest

from api.schemas.sources import AddSourceIn, ChannelSummary, QueueStatusOut


class TestAddSourceIn:
    def test_accepts_username(self):
        m = AddSourceIn(input="@durov")
        assert m.input == "@durov"

    def test_accepts_invite_link(self):
        m = AddSourceIn(input="https://t.me/+abc-DEF_123")
        assert m.input == "https://t.me/+abc-DEF_123"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            AddSourceIn(input="")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError):
            AddSourceIn(input="x" * 300)


class TestChannelSummary:
    def test_is_private_when_username_none(self):
        s = ChannelSummary(id=1, username=None, title="Secret", photo_url=None)
        assert s.is_private is True
        assert s.model_dump()["is_private"] is True

    def test_is_public_when_username_present(self):
        s = ChannelSummary(id=1, username="durov", title="Pavel", photo_url=None)
        assert s.is_private is False


class TestQueueStatusOut:
    def test_accepts_pending_approval(self):
        m = QueueStatusOut(queue_id=1, status="pending_approval", error_code=None, channel=None)
        assert m.status == "pending_approval"

    def test_accepts_error_code(self):
        m = QueueStatusOut(
            queue_id=1, status="failed", error_code="invite_expired", channel=None
        )
        assert m.error_code == "invite_expired"
