import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


@asynccontextmanager
async def _session_cm(session):
    yield session


def test_sweep_leaves_channel_with_zero_refs():
    from ingester import refcount_sweep

    session = MagicMock()
    session.commit = AsyncMock()
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, -100)])
    session.execute = AsyncMock(return_value=targets_result)

    sf = MagicMock()
    sf.side_effect = lambda *a, **kw: _session_cm(session)

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    async def _client_call(req):
        return None
    fake_client.side_effect = _client_call

    with patch("ingester.refcount_sweep.LeaveChannelRequest", lambda e: ("leave", e)):
        asyncio.run(refcount_sweep._sweep_once(fake_client, sf))

    # Two execute calls: one SELECT (returned targets) + one UPDATE (status='left')
    assert session.execute.await_count >= 2


def test_sweep_noop_when_no_targets():
    from ingester import refcount_sweep

    session = MagicMock()
    session.commit = AsyncMock()
    empty_result = MagicMock()
    empty_result.all = MagicMock(return_value=[])
    session.execute = AsyncMock(return_value=empty_result)

    sf = MagicMock()
    sf.side_effect = lambda *a, **kw: _session_cm(session)

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock()

    asyncio.run(refcount_sweep._sweep_once(fake_client, sf))

    fake_client.get_entity.assert_not_called()
