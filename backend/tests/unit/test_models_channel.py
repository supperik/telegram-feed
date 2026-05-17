def test_channel_columns():
    from shared.models import Channel
    cols = {c.name for c in Channel.__table__.columns}
    assert {"id", "tg_chat_id", "username", "title", "description",
            "photo_url", "posts_count", "banned", "banned_reason",
            "created_at", "last_post_at"} <= cols
    assert Channel.__table__.c.tg_chat_id.unique is True
