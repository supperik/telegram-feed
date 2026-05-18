import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@asynccontextmanager
async def _fake_session_cm(session):
    yield session


def _fake_session_factory(session):
    factory = MagicMock()
    # Each call must produce a fresh CM (async CMs are single-shot).
    factory.side_effect = lambda *a, **kw: _fake_session_cm(session)
    return factory


async def _async_empty():
    """Empty async generator, used to stub iter_messages with no results."""
    if False:
        yield


def test_join_worker_happy_path(monkeypatch):
    """Happy path: one pending row → get_entity → join → upsert →
    add_user_source(requester) → done.

    Crucially the requester (pending.requested_by_user_id) MUST get a
    UserSource link so the channel appears in their personal /sources list.
    Otherwise the channel is joined globally but invisible to the user
    who asked for it. ref_count is incremented inside add_user_source
    (was_new=True path), so we do NOT separately call increment_ref_count
    in the join_worker.
    """
    from ingester import join_worker as jw

    pending = MagicMock(
        id=42, channel_username="testchan", channel_id=None,
        requested_by_user_id=11,
    )
    entity = MagicMock(id=-100123, username="testchan", title="Test Chan")
    channel = MagicMock(id=99)

    fake_pop = AsyncMock(side_effect=[pending, None])  # one row, then drain
    fake_get_entity = AsyncMock(return_value=entity)
    fake_upsert_channel = AsyncMock(return_value=channel)
    fake_add_user_source = AsyncMock(return_value=(True, "pending_backfill"))
    fake_inc_ref = AsyncMock()  # MUST stay un-called — see assert_not_called below.
    fake_mark_done = AsyncMock()
    fake_mark_failed = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity
    fake_client.__call__ = AsyncMock()
    fake_client.return_value = None
    async def _client_call(_req):
        return None
    fake_client.side_effect = _client_call
    fake_client.iter_messages = MagicMock(return_value=_async_empty())

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "upsert_channel", fake_upsert_channel)
    monkeypatch.setattr(jw, "add_user_source", fake_add_user_source)
    monkeypatch.setattr(jw, "mark_join_done", fake_mark_done)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)
    monkeypatch.setattr(jw, "JoinChannelRequest", lambda e: ("join", e))

    sf = _fake_session_factory(session)

    async def driver():
        await jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media")
        await jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media")

    asyncio.run(driver())

    fake_pop.assert_awaited()
    fake_get_entity.assert_awaited_once_with("testchan")
    fake_upsert_channel.assert_awaited_once()
    # Requester is linked to the newly joined channel.
    fake_add_user_source.assert_awaited_once_with(session, user_id=11, channel_id=99)
    fake_mark_done.assert_awaited_once_with(session, queue_id=42, channel_id=99)
    fake_mark_failed.assert_not_called()
    fake_client.iter_messages.assert_called_once()


def test_join_worker_handles_username_not_occupied(monkeypatch):
    from telethon.errors import UsernameNotOccupiedError
    from ingester import join_worker as jw

    pending = MagicMock(id=7, channel_username="ghost")

    fake_pop = AsyncMock(return_value=pending)
    fake_get_entity = AsyncMock(side_effect=UsernameNotOccupiedError(None))
    fake_mark_failed = AsyncMock()
    fake_mark_done = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity

    session = MagicMock()
    session.commit = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)
    monkeypatch.setattr(jw, "mark_join_done", fake_mark_done)

    sf = _fake_session_factory(session)
    asyncio.run(jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media"))

    fake_mark_failed.assert_awaited_once()
    args, kwargs = fake_mark_failed.call_args
    assert kwargs["queue_id"] == 7
    assert kwargs["error_code"] == "username_not_occupied"
    assert "username_not_occupied" in kwargs["error_reason"].lower()
    fake_mark_done.assert_not_called()


def test_join_worker_handles_floodwait(monkeypatch):
    """FloodWaitError should NOT mark failed; it sleeps then returns (the loop
    will retry on the next iteration with the same row state). We assert
    asyncio.sleep is awaited with seconds + 1."""
    from telethon.errors import FloodWaitError
    from ingester import join_worker as jw

    pending = MagicMock(id=11, channel_username="busy")
    err = FloodWaitError(None)
    err.seconds = 3

    fake_pop = AsyncMock(return_value=pending)
    fake_get_entity = AsyncMock(side_effect=err)
    fake_mark_failed = AsyncMock()
    fake_mark_done = AsyncMock()
    fake_sleep = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity

    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)
    monkeypatch.setattr(jw, "mark_join_done", fake_mark_done)
    monkeypatch.setattr(jw.asyncio, "sleep", fake_sleep)

    sf = _fake_session_factory(session)
    asyncio.run(jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media"))

    fake_sleep.assert_awaited_once_with(4)  # 3 + 1
    fake_mark_failed.assert_not_called()
    fake_mark_done.assert_not_called()


# ---------------------------------------------------------------------------
# T7 — _join_private flow (Telethon invite-hash branch)
# ---------------------------------------------------------------------------

import ingester.join_worker as jw  # noqa: E402


def _fake_session_factory_t7():
    """Build a fake async session and a context-manager factory.

    Returns (factory, session). `factory()` returns the session; the session
    supports `async with` and has `.commit = AsyncMock()`.
    """
    sess = MagicMock()
    sess.commit = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=sess)
    return factory, sess


class _Row:
    def __init__(self, id=1, invite_hash="abc12345", user_id=42, kind="private_invite"):
        self.id = id
        self.invite_hash = invite_hash
        self.requested_by_user_id = user_id
        self.kind = kind


class _Chat:
    def __init__(self, id=1001, title="Secret", username=None):
        self.id = id
        self.title = title
        self.username = username


@pytest.mark.asyncio
async def test_join_private_happy_path(monkeypatch):
    factory, sess = _fake_session_factory_t7()
    client = MagicMock()
    # CheckChatInviteRequest -> ChatInvite preview (not ChatInviteAlready, not request_needed)
    check_invite = MagicMock()           # plain MagicMock => isinstance ChatInviteAlready == False
    check_invite.request_needed = False
    chat = _Chat()
    updates = MagicMock(chats=[chat])
    client_call = AsyncMock(side_effect=[check_invite, updates])
    monkeypatch.setattr(jw, "_invoke", client_call)
    post_join = AsyncMock(return_value=MagicMock(id=42))
    monkeypatch.setattr(jw, "_post_join", post_join)

    row = _Row()
    result = await jw._join_private(client, factory, row=row)
    assert result is not None
    assert result[0] is chat
    post_join.assert_awaited_once()


@pytest.mark.asyncio
async def test_join_private_chat_invite_already(monkeypatch):
    factory, sess = _fake_session_factory_t7()
    client = MagicMock()
    chat = _Chat(id=2002)
    already = MagicMock(spec=jw.ChatInviteAlready)
    already.chat = chat
    client_call = AsyncMock(return_value=already)
    monkeypatch.setattr(jw, "_invoke", client_call)
    post_join = AsyncMock(return_value=MagicMock(id=42))
    monkeypatch.setattr(jw, "_post_join", post_join)

    row = _Row()
    result = await jw._join_private(client, factory, row=row)
    assert result is not None
    assert result[0] is chat
    post_join.assert_awaited_once()
    # Import was NOT called — only one _invoke call (the Check)
    assert client_call.await_count == 1


@pytest.mark.asyncio
async def test_join_private_request_needed_sent(monkeypatch):
    from telethon.errors import InviteRequestSentError
    factory, _ = _fake_session_factory_t7()
    client = MagicMock()
    invite_preview = MagicMock()
    invite_preview.request_needed = True
    # Check returns preview; Import raises InviteRequestSentError
    client_call = AsyncMock(side_effect=[invite_preview, InviteRequestSentError(request=None)])
    monkeypatch.setattr(jw, "_invoke", client_call)
    mark_pending = AsyncMock()
    monkeypatch.setattr(jw, "mark_pending_approval", mark_pending)

    row = _Row()
    result = await jw._join_private(client, factory, row=row)
    assert result is None
    mark_pending.assert_awaited_once()


@pytest.mark.asyncio
async def test_join_private_invite_hash_invalid(monkeypatch):
    from telethon.errors import InviteHashInvalidError
    factory, _ = _fake_session_factory_t7()
    client = MagicMock()
    client_call = AsyncMock(side_effect=InviteHashInvalidError(request=None))
    monkeypatch.setattr(jw, "_invoke", client_call)
    mark_failed = AsyncMock()
    monkeypatch.setattr(jw, "mark_join_failed", mark_failed)

    row = _Row()
    result = await jw._join_private(client, factory, row=row)
    assert result is None
    mark_failed.assert_awaited_once()
    assert mark_failed.await_args.kwargs["error_code"] == "invite_invalid"


@pytest.mark.asyncio
async def test_join_private_invite_hash_expired(monkeypatch):
    from telethon.errors import InviteHashExpiredError
    factory, _ = _fake_session_factory_t7()
    client = MagicMock()
    client_call = AsyncMock(side_effect=InviteHashExpiredError(request=None))
    monkeypatch.setattr(jw, "_invoke", client_call)
    mark_failed = AsyncMock()
    monkeypatch.setattr(jw, "mark_join_failed", mark_failed)

    row = _Row()
    await jw._join_private(client, factory, row=row)
    assert mark_failed.await_args.kwargs["error_code"] == "invite_expired"


@pytest.mark.asyncio
async def test_join_private_channels_too_much(monkeypatch):
    from telethon.errors import ChannelsTooMuchError
    factory, _ = _fake_session_factory_t7()
    client = MagicMock()
    preview = MagicMock()
    preview.request_needed = False
    client_call = AsyncMock(side_effect=[preview, ChannelsTooMuchError(request=None)])
    monkeypatch.setattr(jw, "_invoke", client_call)
    mark_failed = AsyncMock()
    monkeypatch.setattr(jw, "mark_join_failed", mark_failed)

    row = _Row()
    await jw._join_private(client, factory, row=row)
    assert mark_failed.await_args.kwargs["error_code"] == "channels_too_much"


@pytest.mark.asyncio
async def test_join_private_flood_wait(monkeypatch):
    from telethon.errors import FloodWaitError
    factory, _ = _fake_session_factory_t7()
    client = MagicMock()
    preview = MagicMock()
    preview.request_needed = False
    client_call = AsyncMock(side_effect=[preview, FloodWaitError(request=None, capture=10)])
    monkeypatch.setattr(jw, "_invoke", client_call)
    mark_failed = AsyncMock()
    monkeypatch.setattr(jw, "mark_join_failed", mark_failed)

    row = _Row()
    await jw._join_private(client, factory, row=row)
    assert mark_failed.await_args.kwargs["error_code"] == "flood_wait"


@pytest.mark.asyncio
async def test_join_private_user_already_participant_race(monkeypatch):
    from telethon.errors import UserAlreadyParticipantError
    factory, _ = _fake_session_factory_t7()
    client = MagicMock()
    preview = MagicMock()
    preview.request_needed = False
    chat = _Chat(id=3003)
    already = MagicMock(spec=jw.ChatInviteAlready)
    already.chat = chat
    # 1) Check returns preview (not already); 2) Import raises UserAlreadyParticipant;
    # 3) Re-Check returns ChatInviteAlready
    client_call = AsyncMock(side_effect=[preview, UserAlreadyParticipantError(request=None), already])
    monkeypatch.setattr(jw, "_invoke", client_call)
    post_join = AsyncMock(return_value=MagicMock(id=42))
    monkeypatch.setattr(jw, "_post_join", post_join)

    row = _Row()
    result = await jw._join_private(client, factory, row=row)
    assert result is not None
    assert result[0] is chat
    post_join.assert_awaited_once()
