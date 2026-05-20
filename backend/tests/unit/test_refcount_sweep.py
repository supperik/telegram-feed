import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock


@asynccontextmanager
async def _session_cm(session):
    yield session


def _fake_session_factory(session):
    sf = MagicMock()
    sf.side_effect = lambda *a, **kw: _session_cm(session)
    return sf


def test_sweep_parks_zero_ref_channel_as_dormant():
    """A channel with ref_count==0 and status=='active' is parked as
    `dormant` — its subscription row is updated, no physical leave."""
    from ingester import refcount_sweep

    session = MagicMock()
    session.commit = AsyncMock()
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, 1234567890)])
    session.execute = AsyncMock(return_value=targets_result)

    sf = _fake_session_factory(session)

    asyncio.run(refcount_sweep._sweep_once(sf))

    # Two execute calls: SELECT targets + UPDATE subscription status.
    assert session.execute.await_count == 2
    update_stmt = session.execute.await_args_list[1].args[0]
    compiled = str(update_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "dormant" in compiled
    session.commit.assert_awaited()


def test_sweep_removes_dormant_channel_from_chat_map():
    """The swept channel's marked peer id is dropped from the live chat_map
    so the ingester stops reading it immediately, without a restart."""
    from ingester import refcount_sweep
    from ingester.live import _to_marked_chat_id

    session = MagicMock()
    session.commit = AsyncMock()
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, 1234567890)])
    session.execute = AsyncMock(return_value=targets_result)

    sf = _fake_session_factory(session)
    marked = _to_marked_chat_id(1234567890)
    chat_map = {marked: 7, 555: 1}

    asyncio.run(refcount_sweep._sweep_once(sf, chat_map=chat_map))

    assert chat_map == {555: 1}


def test_sweep_noop_when_no_targets():
    """No ref_count==0 channels → only the SELECT runs, chat_map untouched."""
    from ingester import refcount_sweep

    session = MagicMock()
    session.commit = AsyncMock()
    empty_result = MagicMock()
    empty_result.all = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=empty_result)

    sf = _fake_session_factory(session)
    chat_map = {555: 1}

    asyncio.run(refcount_sweep._sweep_once(sf, chat_map=chat_map))

    assert session.execute.await_count == 1
    assert chat_map == {555: 1}


def test_sweep_never_leaves_channel_physically():
    """Regression guard: the sweep must not import the Telethon leave
    request — parking a channel keeps the userbot a member."""
    from ingester import refcount_sweep

    assert not hasattr(refcount_sweep, "LeaveChannelRequest")
    assert not hasattr(refcount_sweep, "PeerChannel")
