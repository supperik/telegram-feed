from datetime import datetime, timezone
from unittest.mock import MagicMock


def _fake_msg(
    msg_id: int,
    text: str | None = None,
    date: datetime | None = None,
    edit_date: datetime | None = None,
    views: int | None = None,
    forwards: int | None = None,
    photo=None,
    video=None,
    document=None,
):
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text  # Telethon uses .message for text body
    msg.text = text
    msg.date = date or datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)
    msg.edit_date = edit_date
    msg.views = views
    msg.forwards = forwards
    msg.photo = photo
    msg.video = video
    msg.document = document
    msg.entities = None
    msg.grouped_id = None
    return msg


def test_normalize_plain_text():
    from ingester.normalize import normalize_message

    msg = _fake_msg(42, text="hello world", views=100, forwards=5)
    post, media = normalize_message(msg, channel_id=7)

    assert post["channel_id"] == 7
    assert post["tg_message_id"] == 42
    assert post["text"] == "hello world"
    assert post["posted_at"] == datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)
    assert post["edited_at"] is None
    assert post["views"] == 100
    assert post["forwards"] == 5
    assert media == []


def test_normalize_edited():
    from ingester.normalize import normalize_message

    edited = datetime(2026, 5, 17, 13, 0, 0, tzinfo=timezone.utc)
    msg = _fake_msg(43, text="edited", edit_date=edited)
    post, _ = normalize_message(msg, channel_id=7)
    assert post["edited_at"] == edited


def test_normalize_photo():
    from ingester.normalize import normalize_message

    photo = MagicMock(id=9001)
    msg = _fake_msg(44, text="see pic", photo=photo)
    # Telethon photos have .sizes; the largest gives width/height.
    photo.sizes = [MagicMock(w=320, h=240), MagicMock(w=1280, h=960)]
    post, media = normalize_message(msg, channel_id=7)
    assert len(media) == 1
    m = media[0]
    assert m["type"] == "photo"
    assert m["tg_file_id"] == "9001"
    assert m["storage_key"] is None
    assert m["width"] == 1280
    assert m["height"] == 960
    assert m["position"] == 0


def test_normalize_video_has_thumb_and_duration():
    from ingester.normalize import normalize_message

    video = MagicMock(id=7777)
    video.duration = 30
    video.size = 1024 * 1024
    msg = _fake_msg(45, text="vid", video=video)
    msg.file = MagicMock(width=1920, height=1080)
    post, media = normalize_message(msg, channel_id=7)
    assert len(media) == 1
    m = media[0]
    assert m["type"] == "video"
    assert m["tg_file_id"] == "7777"
    assert m["duration"] == 30
    assert m["size_bytes"] == 1024 * 1024


def test_normalize_document():
    from ingester.normalize import normalize_message

    document = MagicMock(id=5555)
    document.size = 4096
    msg = _fake_msg(46, text="doc", document=document)
    post, media = normalize_message(msg, channel_id=7)
    assert len(media) == 1
    m = media[0]
    assert m["type"] == "document"
    assert m["tg_file_id"] == "5555"
    assert m["size_bytes"] == 4096


def test_normalize_no_text_no_media():
    from ingester.normalize import normalize_message

    msg = _fake_msg(47)
    msg.message = None
    msg.text = None
    post, media = normalize_message(msg, channel_id=7)
    assert post["text"] is None
    assert media == []
