import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


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
    fake_download_thumb = AsyncMock()  # not called for photo path

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download)
    monkeypatch.setattr(live, "download_and_store_video_thumb", fake_download_thumb)

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
    fake_download_thumb = AsyncMock()

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download)
    monkeypatch.setattr(live, "download_and_store_video_thumb", fake_download_thumb)

    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    sf = _session_factory(session)

    event = MagicMock()
    event.message = MagicMock(id=1)
    event.chat_id = -100200

    async def run():
        await live.on_new_message(
            event,
            session_factory=sf,
            minio_client=MagicMock(),
            client=MagicMock(),
            channel_id_map={-100200: 7},
            bucket="media",
        )

    asyncio.run(run())

    fake_upsert.assert_awaited_once()
    fake_download.assert_not_awaited()
    fake_download_thumb.assert_not_awaited()


def test_subscribe_to_active_channels_loads_map_and_attaches_handler(monkeypatch):
    """Loads all active channel_subscriptions, builds chat_id -> channel_id map,
    registers a NewMessage handler with chats=list(map)."""
    from ingester import live

    fake_client = MagicMock()
    fake_client.add_event_handler = MagicMock()

    # Two active channels in DB.
    session = MagicMock()
    # We'll patch the SELECT in live._load_active_chat_map.
    fake_load = AsyncMock(return_value={-100111: 1, -100222: 2})
    monkeypatch.setattr(live, "_load_active_chat_map", fake_load)

    sf = _session_factory(session)

    async def run():
        m = await live.subscribe_to_active_channels(
            fake_client, sf, minio_client=MagicMock(), bucket="media"
        )
        return m

    result = asyncio.run(run())

    assert result == {-100111: 1, -100222: 2}
    fake_client.add_event_handler.assert_called_once()
    # Inspect the registered event filter — it should be events.NewMessage(chats=[...])
    args, kwargs = fake_client.add_event_handler.call_args
    # First arg is the handler callable, second is the event builder.
    assert len(args) == 2
    handler_callable = args[0]
    event_filter = args[1]
    # event_filter is an events.NewMessage instance. Check its `chats` attribute.
    assert sorted(event_filter.chats) == [-100222, -100111]


def test_catchup_channels_fetches_missed_messages(monkeypatch):
    """Catchup iterates active channels, calls iter_messages(min_id=max_known),
    upserts every yielded message."""
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        for mid in (10, 11, 12):
            m = MagicMock(id=mid)
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
            fake_client, sf, MagicMock(), bucket="media", limit=100
        )

    asyncio.run(run())

    fake_client.iter_messages.assert_called_once()
    # min_id=5 in the call
    args, kwargs = fake_client.iter_messages.call_args
    assert kwargs.get("min_id") == 5
    assert fake_normalize.call_count == 3
    assert fake_upsert.await_count == 3


def test_catchup_channels_downloads_media_for_new_posts(monkeypatch):
    """Catchup must download photo/video thumbs and set storage_key, matching
    on_new_message behaviour. Regression for: every catchup-inserted Media
    row landed with storage_key=NULL, so /api/media/{id} returned 404."""
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        yield MagicMock(id=10)
        yield MagicMock(id=11)

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
    fake_download_thumb = AsyncMock(return_value="video_thumbs/7/11_v1.jpg")

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download_photo)
    monkeypatch.setattr(live, "download_and_store_video_thumb", fake_download_thumb)

    async def run():
        await live.catchup_channels(
            fake_client, sf, MagicMock(), bucket="media", limit=100
        )

    asyncio.run(run())

    # Both downloads ran exactly once for their respective media types.
    fake_download_photo.assert_awaited_once()
    fake_download_thumb.assert_awaited_once()
    # session.execute is called: 1x for targets SELECT + 1x upsert is mocked +
    # 2x UPDATE Media.storage_key (photo + video). So at minimum 3 executes.
    assert session.execute.await_count >= 3


def test_catchup_channels_skips_download_for_duplicates(monkeypatch):
    """When upsert_post reports a duplicate (returns None), catchup must not
    attempt to download media — same contract as on_new_message."""
    from ingester import live

    fake_client = MagicMock()

    async def gen():
        yield MagicMock(id=10)

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
    fake_download_thumb = AsyncMock()

    monkeypatch.setattr(live, "normalize_message", fake_normalize)
    monkeypatch.setattr(live, "upsert_post", fake_upsert)
    monkeypatch.setattr(live, "download_and_store_photo", fake_download_photo)
    monkeypatch.setattr(live, "download_and_store_video_thumb", fake_download_thumb)

    async def run():
        await live.catchup_channels(
            fake_client, sf, MagicMock(), bucket="media", limit=100
        )

    asyncio.run(run())

    fake_download_photo.assert_not_awaited()
    fake_download_thumb.assert_not_awaited()
