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
    assert post["text_html"] == "hello world"
    assert post["posted_at"] == datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)
    assert post["edited_at"] is None
    assert post["views"] == 100
    assert post["forwards"] == 5
    assert media == []


def test_normalize_none_text_yields_none_text_html():
    from ingester.normalize import normalize_message

    msg = _fake_msg(48)
    msg.message = None
    msg.text = None
    post, _ = normalize_message(msg, channel_id=7)
    assert post["text"] is None
    assert post["text_html"] is None


def test_normalize_entities_produce_text_html():
    from telethon.tl.types import MessageEntityBold, MessageEntityTextUrl

    from ingester.normalize import normalize_message

    msg = _fake_msg(49, text="hello bold link")
    msg.entities = [
        MessageEntityBold(offset=6, length=4),
        MessageEntityTextUrl(offset=11, length=4, url="https://example.com"),
    ]
    post, _ = normalize_message(msg, channel_id=7)
    assert post["text"] == "hello bold link"
    assert "<strong>bold</strong>" in post["text_html"]
    assert 'href="https://example.com"' in post["text_html"]
    assert ">link</a>" in post["text_html"]


def test_normalize_html_specials_in_plain_text_are_escaped():
    from ingester.normalize import normalize_message

    msg = _fake_msg(50, text="<script>alert(1)</script>")
    post, _ = normalize_message(msg, channel_id=7)
    assert post["text"] == "<script>alert(1)</script>"
    assert post["text_html"] == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_normalize_message_with_grouped_id_sets_field():
    """A single message that has grouped_id (e.g. arrived alone) still
    carries the tg_grouped_id into the post dict so subsequent siblings
    can find it."""
    from ingester.normalize import normalize_message

    msg = _fake_msg(60, text="cap")
    msg.grouped_id = 999
    post, _ = normalize_message(msg, channel_id=7)
    assert post["tg_grouped_id"] == 999
    assert post["tg_message_id"] == 60


def test_normalize_album_three_photos_one_post_three_media():
    from ingester.normalize import normalize_album

    p1 = MagicMock(id=1000)
    p1.sizes = [MagicMock(w=800, h=600)]
    p2 = MagicMock(id=1001)
    p2.sizes = [MagicMock(w=1200, h=900)]
    p3 = MagicMock(id=1002)
    p3.sizes = [MagicMock(w=400, h=300)]

    m1 = _fake_msg(100, text="album caption", photo=p1)
    m1.grouped_id = 42
    m2 = _fake_msg(101, photo=p2)
    m2.grouped_id = 42
    m2.message = None
    m2.text = None
    m3 = _fake_msg(102, photo=p3)
    m3.grouped_id = 42
    m3.message = None
    m3.text = None

    post, media = normalize_album([m1, m2, m3], channel_id=7)

    assert post["channel_id"] == 7
    assert post["tg_message_id"] == 100  # min id in group
    assert post["tg_grouped_id"] == 42
    assert post["text"] == "album caption"
    assert post["text_html"] == "album caption"
    assert len(media) == 3
    assert media[0]["tg_file_id"] == str(p1.id)
    assert media[0]["position"] == 0
    assert media[1]["position"] == 1
    assert media[2]["position"] == 2
    # widths preserved
    assert media[0]["width"] == 800
    assert media[1]["width"] == 1200


def test_normalize_album_caption_picked_from_first_nonempty():
    """If the first message has no caption but the second does, the
    second is used."""
    from ingester.normalize import normalize_album

    p1 = MagicMock(id=10)
    p1.sizes = []
    p2 = MagicMock(id=11)
    p2.sizes = []

    m1 = _fake_msg(200, photo=p1)
    m1.message = None
    m1.text = None
    m1.grouped_id = 7
    m2 = _fake_msg(201, text="caption on second", photo=p2)
    m2.grouped_id = 7

    post, _ = normalize_album([m1, m2], channel_id=3)

    assert post["text"] == "caption on second"


def test_normalize_album_orders_media_by_msg_id():
    """If the input list is unsorted, media is still positioned by msg.id."""
    from ingester.normalize import normalize_album

    p_low = MagicMock(id=10)
    p_low.sizes = []
    p_high = MagicMock(id=20)
    p_high.sizes = []

    m_high = _fake_msg(900, photo=p_high)
    m_high.grouped_id = 5
    m_high.message = None
    m_high.text = None
    m_low = _fake_msg(800, text="cap", photo=p_low)
    m_low.grouped_id = 5

    post, media = normalize_album([m_high, m_low], channel_id=1)

    assert post["tg_message_id"] == 800
    assert media[0]["tg_file_id"] == "10"  # photo from msg.id=800 first
    assert media[0]["position"] == 0
    assert media[1]["tg_file_id"] == "20"
    assert media[1]["position"] == 1


def test_normalize_album_text_html_uses_entities_from_caption_message():
    """Entities are picked from the same message whose caption is chosen."""
    from telethon.tl.types import MessageEntityBold

    from ingester.normalize import normalize_album

    p1 = MagicMock(id=1)
    p1.sizes = []
    p2 = MagicMock(id=2)
    p2.sizes = []

    m1 = _fake_msg(300, photo=p1)
    m1.message = None
    m1.text = None
    m1.grouped_id = 88
    m2 = _fake_msg(301, text="hello bold", photo=p2)
    m2.entities = [MessageEntityBold(offset=6, length=4)]
    m2.grouped_id = 88

    post, _ = normalize_album([m1, m2], channel_id=2)

    assert post["text"] == "hello bold"
    assert post["text_html"] == "hello <strong>bold</strong>"


def test_normalize_album_video_and_photo_mix():
    """Album supports mixed photo/video media."""
    from ingester.normalize import normalize_album

    p = MagicMock(id=11)
    p.sizes = []
    v = MagicMock(id=22)
    v.duration = 5
    v.size = 1024

    m1 = _fake_msg(400, text="mixed", photo=p)
    m1.grouped_id = 1
    m2 = _fake_msg(401, video=v)
    m2.file = MagicMock(width=1280, height=720)
    m2.message = None
    m2.text = None
    m2.grouped_id = 1

    post, media = normalize_album([m1, m2], channel_id=4)

    assert len(media) == 2
    assert media[0]["type"] == "photo"
    assert media[1]["type"] == "video"
    assert media[1]["duration"] == 5
    assert post["tg_grouped_id"] == 1


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
