import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


class _S:
    """Stand-in for shared.config.Settings — only the fields the cap-helper reads."""
    video_max_download_bytes = 20 * 1024 * 1024
    video_max_download_seconds = 60


@asynccontextmanager
async def _session_cm(session):
    yield session


def _session_factory(session):
    f = MagicMock()
    f.side_effect = lambda *a, **kw: _session_cm(session)
    return f


def test_on_new_message_normalizes_inserts_and_downloads_photo(monkeypatch):
    from ingester import live

    # Stub the four collaborators imported into ingester.live
    fake_upsert = AsyncMock(return_value=123)  # new post id
    fake_normalize = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 42, "text": "hi",
         "text_html": None, "posted_at": None, "edited_at": None,
         "views": None, "forwards": None},
        [{"type": "photo", "storage_key": None, "tg_file_id": "p1",
          "width": 1, "height": 1, "duration": None,
          "size_bytes": None, "position": 0}],
    ))
    fake_download = AsyncMock(return_value="photos/7/42_p1.jpg")

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download)

    # The handler updates the inserted Media row's storage_key with a SQL UPDATE.
    # We capture that by mocking session.execute.
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    sf = _session_factory(session)

    fake_client = MagicMock()
    fake_minio = MagicMock()

    event = MagicMock()
    event.message = MagicMock(id=42)
    event.message.grouped_id = None
    event.chat_id = -100200

    channel_id_map = {-100200: 7}

    async def run():
        await live.on_new_message(
            event,
            session_factory=sf,
            minio_client=fake_minio,
            client=fake_client,
            channel_id_map=channel_id_map,
            bucket="media",
            settings=_S(),
        )

    asyncio.run(run())

    fake_normalize.assert_called_once_with(event.message, 7)
    fake_upsert.assert_awaited_once()
    fake_download.assert_awaited_once()
    # session.execute called at least once to UPDATE media.storage_key
    assert session.execute.await_count >= 1


def test_on_new_message_skips_duplicate(monkeypatch):
    from ingester import live

    fake_normalize = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 1, "text": "dup",
         "text_html": None, "posted_at": None, "edited_at": None,
         "views": None, "forwards": None},
        [],
    ))
    fake_upsert = AsyncMock(return_value=None)  # already existed
    fake_download = AsyncMock()

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download)

    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    sf = _session_factory(session)

    event = MagicMock()
    event.message = MagicMock(id=1)
    event.message.grouped_id = None
    event.chat_id = -100200

    async def run():
        await live.on_new_message(
            event,
            session_factory=sf,
            minio_client=MagicMock(),
            client=MagicMock(),
            channel_id_map={-100200: 7},
            bucket="media",
            settings=_S(),
        )

    asyncio.run(run())

    fake_upsert.assert_awaited_once()
    fake_download.assert_not_awaited()


def test_subscribe_to_active_channels_loads_map_and_attaches_handler(monkeypatch):
    """Loads all active channel_subscriptions, builds chat_id -> channel_id map
    (with MARKED peer IDs), and registers an unfiltered NewMessage handler.

    No `chats=...` filter on events.NewMessage — Telethon resolves that to a
    static set at subscribe time, which (a) breaks for channels joined after
    boot (telegram-feed-3bv) and (b) historically silently dropped events when
    positive supergroup IDs were passed instead of marked peer IDs. Filtering
    happens inside on_new_message via channel_id_map.get(event.chat_id).
    """
    from ingester import live

    fake_client = MagicMock()
    fake_client.add_event_handler = MagicMock()

    session = MagicMock()
    fake_load = AsyncMock(return_value={-1001111: 1, -1002222: 2})
    monkeypatch.setattr(live, "_load_active_chat_map", fake_load)

    sf = _session_factory(session)

    async def run():
        m = await live.subscribe_to_active_channels(
            fake_client, sf, minio_client=MagicMock(), bucket="media", settings=_S()
        )
        return m

    result = asyncio.run(run())

    assert result == {-1001111: 1, -1002222: 2}
    # Two handlers attached: NewMessage + Album (the latter folds media
    # groups into a single Post). Neither uses a chats=... filter —
    # filtering happens inside on_new_message / on_new_album via
    # channel_id_map.get(event.chat_id).
    assert fake_client.add_event_handler.call_count == 2
    event_filters = [c.args[1] for c in fake_client.add_event_handler.call_args_list]
    type_names = {type(f).__name__ for f in event_filters}
    assert type_names == {"NewMessage", "Album"}
    for f in event_filters:
        assert f.chats is None


def test_to_marked_chat_id_converts_positive_supergroup_to_marked_peer_id():
    """Telegram returns positive supergroup IDs from Channel.id (e.g. 1319248631),
    but Telethon's NewMessage event.chat_id uses the marked peer-id form
    (-1001319248631). _to_marked_chat_id converts the former to the latter,
    matching telethon.utils.get_peer_id(PeerChannel(...))."""
    from telethon.tl.types import PeerChannel
    from telethon.utils import get_peer_id

    from ingester import live

    positive = 1319248631
    expected = get_peer_id(PeerChannel(channel_id=positive))
    assert live._to_marked_chat_id(positive) == expected
    # Sanity: the marked form is negative and starts with -100.
    assert expected == -1001319248631


def test_load_active_chat_map_returns_marked_peer_ids(monkeypatch):
    """_load_active_chat_map must return MARKED peer IDs (-100xxxxx) as keys,
    matching event.chat_id format. Channel.tg_chat_id in the DB is the raw
    positive supergroup ID — the function must normalize on the way out."""
    from ingester import live

    # Simulate SELECT result: rows are (Channel.tg_chat_id, Channel.id) tuples
    # where tg_chat_id is the positive supergroup id.
    rows = [(1319248631, 1), (1966291562, 2)]
    result_mock = MagicMock()
    result_mock.all = MagicMock(return_value=rows)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    sf = _session_factory(session)

    result = asyncio.run(live._load_active_chat_map(sf))

    assert result == {-1001319248631: 1, -1001966291562: 2}


def test_catchup_channels_fetches_missed_messages(monkeypatch):
    """Catchup iterates active channels, calls iter_messages(min_id=max_known),
    upserts every yielded message."""
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        for mid in (10, 11, 12):
            m = MagicMock(id=mid)
            m.grouped_id = None
            yield m

    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_client.iter_messages = MagicMock(return_value=gen())

    # We want a single channel with max_known=5 and 3 new messages.
    session = MagicMock()
    session.commit = AsyncMock()
    sf = _session_factory(session)

    # Patch the session.execute used to load (channel_id, tg_chat_id, max_known) targets.
    # Our session is a MagicMock so we monkey-patch the in-session sequence:
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, -100, 5)])
    session.execute = AsyncMock(return_value=targets_result)

    fake_normalize = MagicMock(return_value=({"channel_id": 7, "tg_message_id": 0,
                                                "text": None, "text_html": None,
                                                "posted_at": None, "edited_at": None,
                                                "views": None, "forwards": None}, []))
    fake_upsert = AsyncMock(return_value=42)
    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)

    async def run():
        await live.catchup_channels(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=100
        )

    asyncio.run(run())

    fake_client.iter_messages.assert_called_once()
    # min_id=5 in the call
    args, kwargs = fake_client.iter_messages.call_args
    assert kwargs.get("min_id") == 5
    assert fake_normalize.call_count == 3
    assert fake_upsert.await_count == 3


def test_catchup_resolves_entity_via_peerchannel(monkeypatch):
    """Regression for 7h6: live.catchup_channels stored Channel.tg_chat_id
    as a positive supergroup id (e.g. 1319248631) and used to pass it
    straight to client.get_entity. Telethon interprets a bare positive
    integer as a PeerUser user_id, so after a cold ingester restart
    (empty in-memory entity cache) it raises "Could not find the input
    entity for PeerUser". Wrapping in PeerChannel(positive_id) is
    unambiguous and resolves via the session-stored access_hash.
    """
    from telethon.tl.types import PeerChannel
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        return
        yield  # generator with no yields

    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_client.iter_messages = MagicMock(return_value=gen())

    session = MagicMock()
    session.commit = AsyncMock()
    sf = _session_factory(session)

    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, 1319248631, 0)])
    session.execute = AsyncMock(return_value=targets_result)

    monkeypatch.setattr(live, "normalize_message", MagicMock())
    monkeypatch.setattr(live, "upsert_post", AsyncMock(return_value=None))

    asyncio.run(live.catchup_channels(
        fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=10,
    ))

    fake_client.get_entity.assert_awaited_once()
    arg = fake_client.get_entity.await_args.args[0]
    assert isinstance(arg, PeerChannel), (
        f"get_entity must receive PeerChannel, got {type(arg).__name__}: {arg!r}"
    )
    assert arg.channel_id == 1319248631


def test_catchup_channels_downloads_photo_but_skips_video(monkeypatch):
    """Catchup downloads photos and sets their storage_key. Videos are
    intentionally NOT downloaded — the TMA renders a compact "open in
    Telegram" link for them — so no UPDATE is issued for video media rows.
    """
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        m1 = MagicMock(id=10)
        m1.grouped_id = None
        m2 = MagicMock(id=11)
        m2.grouped_id = None
        yield m1
        yield m2

    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_client.iter_messages = MagicMock(return_value=gen())

    session = MagicMock()
    session.commit = AsyncMock()
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, -100, 5)])
    session.execute = AsyncMock(return_value=targets_result)
    sf = _session_factory(session)

    photo_media = {"type": "photo", "storage_key": None, "tg_file_id": "p1",
                   "width": 1, "height": 1, "duration": None,
                   "size_bytes": None, "position": 0}
    video_media = {"type": "video", "storage_key": None, "tg_file_id": "v1",
                   "width": 2, "height": 2, "duration": 5,
                   "size_bytes": None, "position": 0}
    fake_normalize = MagicMock(side_effect=[
        ({"channel_id": 7, "tg_message_id": 10, "text": None, "text_html": None,
          "posted_at": None, "edited_at": None, "views": None, "forwards": None},
         [photo_media]),
        ({"channel_id": 7, "tg_message_id": 11, "text": None, "text_html": None,
          "posted_at": None, "edited_at": None, "views": None, "forwards": None},
         [video_media]),
    ])
    fake_upsert = AsyncMock(return_value=42)
    fake_download_photo = AsyncMock(return_value="photos/7/10_p1.jpg")

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download_photo)

    async def run():
        await live.catchup_channels(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=100
        )

    asyncio.run(run())

    # Photo downloaded once. Video never reaches a downloader.
    fake_download_photo.assert_awaited_once()


def test_catchup_channels_skips_download_for_duplicates(monkeypatch):
    """When upsert_post reports a duplicate (returns None), catchup must not
    attempt to download media — same contract as on_new_message."""
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        m = MagicMock(id=10)
        m.grouped_id = None
        yield m

    fake_client.get_entity = AsyncMock(return_value=MagicMock())
    fake_client.iter_messages = MagicMock(return_value=gen())

    session = MagicMock()
    session.commit = AsyncMock()
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, -100, 5)])
    session.execute = AsyncMock(return_value=targets_result)
    sf = _session_factory(session)

    fake_normalize = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 10, "text": None, "text_html": None,
         "posted_at": None, "edited_at": None, "views": None, "forwards": None},
        [{"type": "photo", "storage_key": None, "tg_file_id": "p1",
          "width": 1, "height": 1, "duration": None,
          "size_bytes": None, "position": 0}],
    ))
    fake_upsert = AsyncMock(return_value=None)  # duplicate
    fake_download_photo = AsyncMock()

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download_photo)

    async def run():
        await live.catchup_channels(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=100
        )

    asyncio.run(run())

    fake_download_photo.assert_not_awaited()


def test_on_new_message_skips_grouped_messages(monkeypatch):
    """Album parts are handled by on_new_album. on_new_message must not
    create individual Posts for them — otherwise an album of N items
    yields N separate cards in the feed."""
    from ingester import live

    fake_normalize = MagicMock()
    fake_upsert = AsyncMock()
    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)

    session = MagicMock()
    sf = _session_factory(session)

    event = MagicMock()
    event.message = MagicMock(id=42)
    event.message.grouped_id = 999  # part of an album
    event.chat_id = -100200

    async def run():
        await live.on_new_message(
            event,
            session_factory=sf,
            minio_client=MagicMock(),
            client=MagicMock(),
            channel_id_map={-100200: 7},
            bucket="media",
            settings=_S(),
        )

    asyncio.run(run())

    fake_normalize.assert_not_called()
    fake_upsert.assert_not_awaited()


def test_on_new_album_normalizes_inserts_and_downloads(monkeypatch):
    """An events.Album event with 3 photo messages becomes a single Post
    with 3 Media (positions 0,1,2). Each media file is downloaded."""
    from ingester import live

    msgs = [MagicMock(id=100), MagicMock(id=101), MagicMock(id=102)]
    for m in msgs:
        m.grouped_id = 42

    fake_normalize_album = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 100, "tg_grouped_id": 42,
         "text": "alb", "text_html": "alb", "posted_at": None,
         "edited_at": None, "views": None, "forwards": None},
        [
            {"type": "photo", "storage_key": None, "tg_file_id": "p1",
             "width": 1, "height": 1, "duration": None,
             "size_bytes": None, "position": 0},
            {"type": "photo", "storage_key": None, "tg_file_id": "p2",
             "width": 1, "height": 1, "duration": None,
             "size_bytes": None, "position": 1},
            {"type": "photo", "storage_key": None, "tg_file_id": "p3",
             "width": 1, "height": 1, "duration": None,
             "size_bytes": None, "position": 2},
        ],
    ))
    fake_upsert = AsyncMock(return_value=500)
    fake_download_photo = AsyncMock(return_value="photos/7/100_p.jpg")

    monkeypatch.setattr(live, "normalize_album", fake_normalize_album)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download_photo)

    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    sf = _session_factory(session)

    event = MagicMock()
    event.messages = msgs
    event.chat_id = -100200

    async def run():
        await live.on_new_album(
            event,
            session_factory=sf,
            minio_client=MagicMock(),
            client=MagicMock(),
            channel_id_map={-100200: 7},
            bucket="media",
            settings=_S(),
        )

    asyncio.run(run())

    fake_normalize_album.assert_called_once_with(msgs, 7)
    fake_upsert.assert_awaited_once()
    # Three photos → three downloads.
    assert fake_download_photo.await_count == 3


def test_on_new_album_unknown_chat_id_is_noop(monkeypatch):
    from ingester import live

    fake_normalize_album = MagicMock()
    monkeypatch.setattr(live, "normalize_album", fake_normalize_album)

    event = MagicMock()
    event.messages = [MagicMock(id=1)]
    event.chat_id = -100200  # not in map

    async def run():
        await live.on_new_album(
            event,
            session_factory=_session_factory(MagicMock()),
            minio_client=MagicMock(),
            client=MagicMock(),
            channel_id_map={},
            bucket="media",
            settings=_S(),
        )

    asyncio.run(run())

    fake_normalize_album.assert_not_called()


def test_catchup_groups_album_messages_into_single_post(monkeypatch):
    """Three messages with the same grouped_id arrive via iter_messages →
    catchup folds them into a single normalize_album call (one Post, 3 media)."""
    from ingester import live

    fake_client = MagicMock()
    fake_client.get_entity = AsyncMock(return_value=MagicMock())

    async def gen():
        m1 = MagicMock(id=20)
        m1.grouped_id = 42
        m2 = MagicMock(id=21)
        m2.grouped_id = 42
        m3 = MagicMock(id=22)
        m3.grouped_id = 42
        solo = MagicMock(id=23)
        solo.grouped_id = None
        yield m1
        yield m2
        yield m3
        yield solo

    fake_client.iter_messages = MagicMock(return_value=gen())

    session = MagicMock()
    session.commit = AsyncMock()
    targets_result = MagicMock()
    targets_result.all = MagicMock(return_value=[(7, -100, 5)])
    session.execute = AsyncMock(return_value=targets_result)
    sf = _session_factory(session)

    fake_normalize_msg = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 23, "tg_grouped_id": None,
         "text": None, "text_html": None, "posted_at": None,
         "edited_at": None, "views": None, "forwards": None},
        [],
    ))
    fake_normalize_album = MagicMock(return_value=(
        {"channel_id": 7, "tg_message_id": 20, "tg_grouped_id": 42,
         "text": "alb", "text_html": "alb", "posted_at": None,
         "edited_at": None, "views": None, "forwards": None},
        [],
    ))
    fake_upsert = AsyncMock(return_value=200)
    monkeypatch.setattr(live, "normalize_message", fake_normalize_msg)
    monkeypatch.setattr(live, "normalize_album", fake_normalize_album)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)

    async def run():
        await live.catchup_channels(
            fake_client, sf, MagicMock(), bucket="media", settings=_S(), limit=200
        )

    asyncio.run(run())

    # Album call: once with all three messages (any order).
    fake_normalize_album.assert_called_once()
    album_msgs = fake_normalize_album.call_args.args[0]
    assert sorted(m.id for m in album_msgs) == [20, 21, 22]
    # Solo call: once with the single message id=23.
    fake_normalize_msg.assert_called_once()
    assert fake_normalize_msg.call_args.args[0].id == 23
    # Two upserts total: one album + one solo.
    assert fake_upsert.await_count == 2


def test_subscribe_to_active_channels_registers_album_handler_too(monkeypatch):
    """Both events.NewMessage and events.Album handlers must be registered
    so albums become single posts with N media."""
    from telethon import events
    from ingester import live

    fake_client = MagicMock()
    fake_client.add_event_handler = MagicMock()
    monkeypatch.setattr(live, "_load_active_chat_map",
                        AsyncMock(return_value={-100: 1}))

    sf = _session_factory(MagicMock())

    async def run():
        await live.subscribe_to_active_channels(
            fake_client, sf, minio_client=MagicMock(), bucket="media", settings=_S()
        )

    asyncio.run(run())

    # Two calls: one for NewMessage, one for Album. Neither uses a
    # chats=... filter — filtering is done inside the handlers via
    # channel_id_map.get(event.chat_id).
    assert fake_client.add_event_handler.call_count == 2
    event_filters = [c.args[1] for c in fake_client.add_event_handler.call_args_list]
    builders = {type(f).__name__ for f in event_filters}
    assert "NewMessage" in builders
    assert "Album" in builders
    for ef in event_filters:
        assert isinstance(ef, (events.NewMessage, events.Album))
        assert ef.chats is None
