from datetime import datetime, timezone
from types import SimpleNamespace


def _msg(msg_id: int, dt: datetime | None = None, grouped_id: int | None = None):
    return SimpleNamespace(id=msg_id, date=dt, grouped_id=grouped_id)


class _FakeClient:
    """Minimal Telethon stand-in. iter_messages yields the given messages in
    order (newest first, like Telethon's default) as an async generator."""

    def __init__(self, messages: list):
        self._messages = messages
        self.calls: list = []

    def iter_messages(self, entity, **kwargs):
        self.calls.append((entity, kwargs))
        messages = self._messages

        async def _gen():
            for m in messages:
                yield m

        return _gen()


def test_cutoff_from_subtracts_days():
    from ingester.last_days_backfill import cutoff_from

    now = datetime(2026, 6, 9, 8, 0, 0, tzinfo=timezone.utc)
    assert cutoff_from(now, 8) == datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


def test_split_albums_solos_groups_by_grouped_id():
    from ingester.last_days_backfill import split_albums_solos

    a1 = _msg(1, grouped_id=42)
    a2 = _msg(2, grouped_id=42)
    b1 = _msg(3, grouped_id=99)
    s1 = _msg(4, grouped_id=None)

    albums, solos = split_albums_solos([a1, a2, b1, s1])

    assert albums == {42: [a1, a2], 99: [b1]}
    assert solos == [s1]


def test_split_albums_solos_all_solo():
    from ingester.last_days_backfill import split_albums_solos

    msgs = [_msg(1), _msg(2)]
    albums, solos = split_albums_solos(msgs)
    assert albums == {}
    assert solos == msgs


async def test_collect_window_stops_at_first_older_message():
    from ingester.last_days_backfill import collect_window

    cutoff = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    newest = _msg(100, datetime(2026, 6, 9, tzinfo=timezone.utc))
    mid = _msg(99, datetime(2026, 6, 2, tzinfo=timezone.utc))
    older = _msg(98, datetime(2026, 5, 31, tzinfo=timezone.utc))  # < cutoff -> stop
    even_older = _msg(97, datetime(2026, 5, 1, tzinfo=timezone.utc))
    client = _FakeClient([newest, mid, older, even_older])

    collected = await collect_window(client, entity="e", cutoff=cutoff)

    assert [m.id for m in collected] == [100, 99]


async def test_collect_window_includes_message_exactly_at_cutoff():
    from ingester.last_days_backfill import collect_window

    cutoff = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    at_cutoff = _msg(50, datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc))  # == cutoff -> kept
    older = _msg(49, datetime(2026, 5, 30, tzinfo=timezone.utc))
    client = _FakeClient([at_cutoff, older])

    collected = await collect_window(client, entity="e", cutoff=cutoff)

    assert [m.id for m in collected] == [50]


async def test_collect_window_empty_channel():
    from ingester.last_days_backfill import collect_window

    cutoff = datetime(2026, 6, 1, tzinfo=timezone.utc)
    client = _FakeClient([])

    collected = await collect_window(client, entity="e", cutoff=cutoff)

    assert collected == []
