def test_post_columns_and_constraints():
    from shared.models import Post
    cols = {c.name for c in Post.__table__.columns}
    assert {"id", "channel_id", "tg_message_id", "text", "text_html",
            "posted_at", "edited_at", "views", "forwards", "fetched_at"} <= cols
    uniques = [tuple(c.columns.keys()) for c in Post.__table__.constraints
               if c.__class__.__name__ == "UniqueConstraint"]
    assert ("channel_id", "tg_message_id") in uniques


def test_media_columns():
    from shared.models import Media
    cols = {c.name for c in Media.__table__.columns}
    assert {"id", "post_id", "type", "storage_key", "tg_file_id",
            "width", "height", "duration", "size_bytes", "position"} <= cols
