from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import ingester.approval_poller as ap


class _S:
    """Stand-in for shared.config.Settings — only the fields the cap-helper reads."""
    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


def _row(*, id=1, invite_hash="abc12345", user_id=42, age_days=0):
    r = MagicMock()
    r.id = id
    r.invite_hash = invite_hash
    r.requested_by_user_id = user_id
    r.updated_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    return r


def _factory():
    sess = MagicMock()
    sess.commit = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=sess), sess


@pytest.mark.asyncio
async def test_pending_chat_invite_still_pending_does_nothing(monkeypatch):
    """Row is pending_approval, Check returns ChatInvite (preview) - no state change."""
    factory, sess = _factory()
    client = MagicMock()
    fetch = AsyncMock(return_value=[_row(age_days=1)])
    monkeypatch.setattr(ap, "fetch_pending_approval", fetch)
    invite_preview = MagicMock()
    monkeypatch.setattr(ap, "_invoke", AsyncMock(return_value=invite_preview))
    post_join = AsyncMock()
    mark_failed = AsyncMock()
    monkeypatch.setattr(ap, "_post_join", post_join)
    monkeypatch.setattr(ap, "mark_join_failed", mark_failed)

    await ap._approval_poll_once(client, factory, minio_client=MagicMock(),
                                 bucket="b", timeout_days=7, settings=_S())
    post_join.assert_not_awaited()
    mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_invite_already_triggers_post_join(monkeypatch):
    factory, sess = _factory()
    client = MagicMock()
    fetch = AsyncMock(return_value=[_row(age_days=1)])
    monkeypatch.setattr(ap, "fetch_pending_approval", fetch)
    chat = MagicMock(id=9001, title="Approved", username=None)
    already = MagicMock(spec=ap.ChatInviteAlready)
    already.chat = chat
    monkeypatch.setattr(ap, "_invoke", AsyncMock(return_value=already))
    post_join = AsyncMock(return_value=MagicMock(id=10))
    monkeypatch.setattr(ap, "_post_join", post_join)
    backfill = AsyncMock()
    monkeypatch.setattr(ap, "_backfill_channel", backfill)

    await ap._approval_poll_once(client, factory, minio_client=MagicMock(),
                                 bucket="b", timeout_days=7, settings=_S())
    post_join.assert_awaited_once()
    backfill.assert_awaited_once()


@pytest.mark.asyncio
async def test_timeout_marks_failed(monkeypatch):
    factory, sess = _factory()
    client = MagicMock()
    old_row = _row(age_days=8)
    fetch = AsyncMock(return_value=[old_row])
    monkeypatch.setattr(ap, "fetch_pending_approval", fetch)
    invoke = AsyncMock()  # should NOT be called
    monkeypatch.setattr(ap, "_invoke", invoke)
    mark_failed = AsyncMock()
    monkeypatch.setattr(ap, "mark_join_failed", mark_failed)

    await ap._approval_poll_once(client, factory, minio_client=MagicMock(),
                                 bucket="b", timeout_days=7, settings=_S())
    invoke.assert_not_awaited()
    mark_failed.assert_awaited_once()
    assert mark_failed.await_args.kwargs["error_code"] == "approval_timeout"


@pytest.mark.asyncio
async def test_expired_hash_marks_failed(monkeypatch):
    from telethon.errors import InviteHashExpiredError
    factory, _ = _factory()
    client = MagicMock()
    fetch = AsyncMock(return_value=[_row(age_days=1)])
    monkeypatch.setattr(ap, "fetch_pending_approval", fetch)
    monkeypatch.setattr(ap, "_invoke", AsyncMock(side_effect=InviteHashExpiredError(request=None)))
    mark_failed = AsyncMock()
    monkeypatch.setattr(ap, "mark_join_failed", mark_failed)

    await ap._approval_poll_once(client, factory, minio_client=MagicMock(),
                                 bucket="b", timeout_days=7, settings=_S())
    assert mark_failed.await_args.kwargs["error_code"] == "invite_expired"
