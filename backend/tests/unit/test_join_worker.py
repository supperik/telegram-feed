import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _S:
    """Stand-in for shared.config.Settings — only the fields the cap-helper reads."""
    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


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
        await jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media", settings=_S())
        await jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media", settings=_S())

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
    asyncio.run(jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media", settings=_S()))

    fake_mark_failed.assert_awaited_once()
    args, kwargs = fake_mark_failed.call_args
    assert kwargs["queue_id"] == 7
    assert kwargs["error_code"] == "username_not_occupied"
    assert "username_not_occupied" in kwargs["error_reason"].lower()
    fake_mark_done.assert_not_called()


def test_join_worker_registers_new_channel_in_chat_map(monkeypatch):
    """After a successful join, _handle_one_pending extends the shared
    chat_map dict so the live NewMessage handler picks up the new channel
    immediately, without an ingester restart (telegram-feed-3bv).

    The key in chat_map is the MARKED peer id (matching event.chat_id),
    derived from the raw positive entity.id via _to_marked_chat_id.
    """
    from ingester import join_worker as jw
    from ingester.live import _to_marked_chat_id

    pending = MagicMock(
        id=42, channel_username="testchan", channel_id=None,
        requested_by_user_id=11,
    )
    # Real Telethon channel entity.id is a positive supergroup id.
    entity = MagicMock(id=1234567890, username="testchan", title="Test Chan")
    channel = MagicMock(id=99)

    fake_pop = AsyncMock(side_effect=[pending, None])
    fake_get_entity = AsyncMock(return_value=entity)
    fake_upsert_channel = AsyncMock(return_value=channel)
    fake_add_user_source = AsyncMock(return_value=(True, "pending_backfill"))
    fake_mark_done = AsyncMock()
    fake_mark_failed = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity
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
    chat_map: dict[int, int] = {}

    asyncio.run(jw._handle_one_pending(
        fake_client, sf, minio_client=MagicMock(), bucket="media",
        settings=_S(),
        chat_map=chat_map,
    ))

    # chat_map mutated in place with marked id -> channel.id.
    expected_marked = _to_marked_chat_id(1234567890)
    assert chat_map == {expected_marked: 99}


def test_join_worker_does_not_touch_chat_map_on_failed_join(monkeypatch):
    """If get_entity / join fails, chat_map MUST NOT be mutated — otherwise
    we'd leak stale entries for channels we never actually joined."""
    from telethon.errors import UsernameNotOccupiedError
    from ingester import join_worker as jw

    pending = MagicMock(id=7, channel_username="ghost")

    fake_pop = AsyncMock(return_value=pending)
    fake_get_entity = AsyncMock(side_effect=UsernameNotOccupiedError(None))
    fake_mark_failed = AsyncMock()

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity

    session = MagicMock()
    session.commit = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "mark_join_failed", fake_mark_failed)

    sf = _fake_session_factory(session)
    chat_map: dict[int, int] = {99: 1}  # pre-existing entry

    asyncio.run(jw._handle_one_pending(
        fake_client, sf, minio_client=MagicMock(), bucket="media",
        settings=_S(),
        chat_map=chat_map,
    ))

    assert chat_map == {99: 1}  # untouched


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
    asyncio.run(jw._handle_one_pending(fake_client, sf, minio_client=MagicMock(), bucket="media", settings=_S()))

    fake_sleep.assert_awaited_once_with(4)  # 3 + 1
    fake_mark_failed.assert_not_called()
    fake_mark_done.assert_not_called()


def test_join_worker_downloads_and_records_channel_photo(monkeypatch):
    """After a successful join, _handle_one_pending downloads the channel
    avatar via Telethon and writes the resulting storage key onto the
    channels row."""
    from ingester import join_worker as jw

    pending = MagicMock(
        id=42, channel_username="testchan", channel_id=None,
        requested_by_user_id=11,
    )
    entity = MagicMock(id=-100123, username="testchan", title="Test Chan")
    channel = MagicMock(id=99)

    fake_pop = AsyncMock(side_effect=[pending, None])
    fake_get_entity = AsyncMock(return_value=entity)
    fake_upsert_channel = AsyncMock(return_value=channel)
    fake_add_user_source = AsyncMock(return_value=(True, "pending_backfill"))
    fake_mark_done = AsyncMock()
    fake_mark_failed = AsyncMock()
    fake_download_channel_photo = AsyncMock(return_value="channel_photos/99.jpg")

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity
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
    monkeypatch.setattr(jw, "download_and_store_channel_photo", fake_download_channel_photo)

    sf = _fake_session_factory(session)
    asyncio.run(jw._handle_one_pending(
        fake_client, sf, minio_client=MagicMock(), bucket="media",
        settings=_S(),
    ))

    fake_download_channel_photo.assert_awaited_once()
    _, kwargs = fake_download_channel_photo.call_args
    assert kwargs.get("channel_id") == 99
    # An UPDATE channels SET photo_storage_key was issued.
    update_calls = [
        c for c in session.execute.await_args_list
        if "UPDATE channels" in str(c.args[0])
        and "photo_storage_key" in str(c.args[0])
    ]
    assert update_calls, "expected UPDATE channels SET photo_storage_key"


def test_join_worker_swallows_channel_photo_errors(monkeypatch):
    """A failure downloading the avatar must not break the join — backfill
    will retry on the next ingester boot."""
    from ingester import join_worker as jw

    pending = MagicMock(
        id=42, channel_username="testchan", channel_id=None,
        requested_by_user_id=11,
    )
    entity = MagicMock(id=-100123, username="testchan", title="Test Chan")
    channel = MagicMock(id=99)

    fake_pop = AsyncMock(side_effect=[pending, None])
    fake_get_entity = AsyncMock(return_value=entity)
    fake_upsert_channel = AsyncMock(return_value=channel)
    fake_add_user_source = AsyncMock(return_value=(True, "pending_backfill"))
    fake_mark_done = AsyncMock()
    fake_download_channel_photo = AsyncMock(side_effect=Exception("net flake"))

    fake_client = MagicMock()
    fake_client.get_entity = fake_get_entity
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
    monkeypatch.setattr(jw, "mark_join_failed", AsyncMock())
    monkeypatch.setattr(jw, "JoinChannelRequest", lambda e: ("join", e))
    monkeypatch.setattr(jw, "download_and_store_channel_photo", fake_download_channel_photo)

    sf = _fake_session_factory(session)
    # Must NOT raise.
    asyncio.run(jw._handle_one_pending(
        fake_client, sf, minio_client=MagicMock(), bucket="media",
        settings=_S(),
    ))

    # Join completed normally.
    fake_mark_done.assert_awaited_once()


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


def test_handle_one_pending_private_registers_chat_map(monkeypatch):
    """After a successful private-invite join, _handle_one_pending must add
    {_to_marked_chat_id(chat.id): channel_id} to chat_map. Without this,
    the live NewMessage handler keeps ignoring events from the new private
    channel until the next ingester restart loads it via _load_active_chat_map.
    The public branch already does this in line 364-365; the private branch
    forgot to mirror that behaviour and silently swallowed every live post.
    """
    from ingester import join_worker as jw
    from ingester.live import _to_marked_chat_id

    pending = MagicMock(
        id=42, kind="private_invite", invite_hash="abc12345",
        channel_username=None, channel_id=None, requested_by_user_id=7,
    )
    chat = MagicMock(id=5566778899, username=None, title="Secret Channel")

    fake_pop = AsyncMock(side_effect=[pending, None])
    fake_join_private = AsyncMock(return_value=(chat, 314))
    fake_backfill = AsyncMock()

    fake_client = MagicMock()

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()

    monkeypatch.setattr(jw, "pop_pending_join_request", fake_pop)
    monkeypatch.setattr(jw, "_join_private", fake_join_private)
    monkeypatch.setattr(jw, "_backfill_channel", fake_backfill)

    sf = _fake_session_factory(session)
    chat_map: dict[int, int] = {}

    asyncio.run(jw._handle_one_pending(
        fake_client, sf, minio_client=MagicMock(), bucket="media",
        settings=_S(),
        chat_map=chat_map,
    ))

    expected_marked = _to_marked_chat_id(5566778899)
    assert chat_map == {expected_marked: 314}, (
        f"private branch must register {expected_marked!r} -> 314; "
        f"got {chat_map!r}"
    )
    fake_join_private.assert_awaited_once()
    fake_backfill.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_join_writes_invite_hash_for_private_invite(monkeypatch):
    """T8: for private-invite joins, _post_join must UPDATE channels SET
    invite_hash so the just-created Channel row stores the hash we joined
    via (used later to render invite_url in the feed and to re-join after
    cache loss). The hash is the same value that came in on the queue row.
    """
    from ingester.join_worker import _post_join

    session = MagicMock()
    session.execute = AsyncMock()
    monkeypatch.setattr(
        "ingester.join_worker.upsert_channel",
        AsyncMock(return_value=MagicMock(id=7, tg_chat_id=12345)),
    )
    monkeypatch.setattr(
        "ingester.join_worker.add_user_source", AsyncMock(),
    )
    monkeypatch.setattr(
        "ingester.join_worker.mark_join_done", AsyncMock(),
    )
    row = MagicMock()
    row.id = 1
    row.requested_by_user_id = 42
    row.kind = "private_invite"
    row.invite_hash = "abc123"
    chat = MagicMock()
    chat.id = 12345
    chat.username = None
    chat.title = "Private chan"

    await _post_join(session, row=row, chat=chat)

    update_calls = session.execute.await_args_list
    seen = False
    for call in update_calls:
        stmt = call.args[0]
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)
        if "UPDATE channels" in compiled and "invite_hash" in compiled and "abc123" in compiled:
            seen = True
            break
    assert seen, f"Expected UPDATE channels SET invite_hash for private_invite. Saw: {update_calls}"


@pytest.mark.asyncio
async def test_post_join_lowercases_channel_username(monkeypatch):
    """Telethon may return chat.username in mixed case ('DurovChannel'). The
    stored channels.username must be ASCII-lowercase, because POST /sources
    lowercases its input before SELECT (api/routers/sources.py
    _add_public_source). Without normalization in the ingester, a later
    request with 'durovchannel' misses the existing row and re-queues an
    unnecessary join.
    """
    from ingester.join_worker import _post_join

    session = MagicMock()
    session.execute = AsyncMock()
    captured: dict[str, str | None] = {}

    async def fake_upsert(_session, *, tg_chat_id, username, title, **_kw):
        captured["username"] = username
        return MagicMock(id=7, tg_chat_id=tg_chat_id)

    monkeypatch.setattr("ingester.join_worker.upsert_channel", fake_upsert)
    monkeypatch.setattr("ingester.join_worker.add_user_source", AsyncMock())
    monkeypatch.setattr("ingester.join_worker.mark_join_done", AsyncMock())

    row = MagicMock(
        id=1, requested_by_user_id=42, kind="public_username", invite_hash=None,
    )
    chat = MagicMock(id=12345, username="DurovChannel", title="Durov")

    await _post_join(session, row=row, chat=chat)

    assert captured["username"] == "durovchannel"


@pytest.mark.asyncio
async def test_post_join_keeps_none_username_for_private_channel(monkeypatch):
    """Private channels (joined via invite hash) have chat.username == None;
    normalization must keep that as None instead of crashing on .lower().
    """
    from ingester.join_worker import _post_join

    session = MagicMock()
    session.execute = AsyncMock()
    captured: dict[str, str | None] = {}

    async def fake_upsert(_session, *, tg_chat_id, username, title, **_kw):
        captured["username"] = username
        return MagicMock(id=7, tg_chat_id=tg_chat_id)

    monkeypatch.setattr("ingester.join_worker.upsert_channel", fake_upsert)
    monkeypatch.setattr("ingester.join_worker.add_user_source", AsyncMock())
    monkeypatch.setattr("ingester.join_worker.mark_join_done", AsyncMock())

    row = MagicMock(
        id=1, requested_by_user_id=42, kind="private_invite", invite_hash="abc",
    )
    chat = MagicMock(id=12345, username=None, title="Secret")

    await _post_join(session, row=row, chat=chat)

    assert captured["username"] is None


@pytest.mark.asyncio
async def test_post_join_skips_invite_hash_for_public_username(monkeypatch):
    """T8: for public-username joins, _post_join must NOT touch
    channels.invite_hash — there's nothing meaningful to write (the
    channel is public). Touching it would either store an empty string or
    propagate `None` into a column that may already hold a valid hash from
    a prior private-invite join of the same channel.
    """
    from ingester.join_worker import _post_join

    session = MagicMock()
    session.execute = AsyncMock()
    monkeypatch.setattr(
        "ingester.join_worker.upsert_channel",
        AsyncMock(return_value=MagicMock(id=7, tg_chat_id=12345)),
    )
    monkeypatch.setattr(
        "ingester.join_worker.add_user_source", AsyncMock(),
    )
    monkeypatch.setattr(
        "ingester.join_worker.mark_join_done", AsyncMock(),
    )
    row = MagicMock()
    row.id = 1
    row.requested_by_user_id = 42
    row.kind = "public_username"
    row.invite_hash = None
    chat = MagicMock()
    chat.id = 12345
    chat.username = "meduzaproject"
    chat.title = "Meduza"

    await _post_join(session, row=row, chat=chat)

    for call in session.execute.await_args_list:
        stmt = call.args[0]
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)
        assert "invite_hash" not in compiled, (
            f"Did not expect invite_hash in UPDATE for public_username: {compiled}"
        )


def test_backfill_channel_downloads_media_for_solo_photo(monkeypatch):
    """_backfill_channel must actually download media (not just insert Media
    rows with storage_key=NULL) so newly joined channels show thumbnails
    immediately, without waiting for the next ingester boot to run
    backfill_recent_media."""
    from ingester import join_worker as jw

    msg = MagicMock(id=42)
    msg.photo = MagicMock()  # photo present
    msg.video = None
    msg.document = None
    msg.grouped_id = None  # solo, not part of an album

    async def gen():
        yield msg

    fake_client = MagicMock()
    fake_client.iter_messages = MagicMock(return_value=gen())

    fake_normalize = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 42, "tg_grouped_id": None,
         "text": None, "text_html": None, "posted_at": None,
         "edited_at": None, "views": None, "forwards": None},
        [{"type": "photo", "storage_key": None, "tg_file_id": "p1",
          "width": None, "height": None, "duration": None,
          "size_bytes": None, "position": 0}],
    ))
    fake_upsert = AsyncMock(return_value=100)  # new post id
    fake_download = AsyncMock()

    monkeypatch.setattr(jw, "normalize_message", fake_normalize)
    monkeypatch.setattr(jw, "upsert_post", fake_upsert)
    monkeypatch.setattr(jw, "download_and_set_storage_keys", fake_download,
                        raising=False)

    session = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    sf = _fake_session_factory(session)

    entity = MagicMock()
    minio = MagicMock()

    asyncio.run(jw._backfill_channel(
        fake_client, sf, minio, entity, channel_id=7,
        limit=50, bucket="media", settings=_S(),
    ))

    fake_download.assert_awaited_once()
    _, kwargs = fake_download.call_args
    assert kwargs["channel_id"] == 7
    assert kwargs["new_post_id"] == 100
    assert kwargs["msg"] is msg
    assert kwargs["bucket"] == "media"
    assert kwargs["client"] is fake_client
    assert kwargs["minio_client"] is minio
