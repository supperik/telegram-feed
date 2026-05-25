def test_channel_columns():
    from shared.models import Channel
    cols = {c.name for c in Channel.__table__.columns}
    assert {"id", "tg_chat_id", "username", "title", "description",
            "photo_storage_key", "posts_count", "banned", "banned_reason",
            "created_at", "last_post_at"} <= cols
    assert Channel.__table__.c.tg_chat_id.unique is True


def test_channel_category_link_columns():
    from shared.models import ChannelCategoryLink

    table = ChannelCategoryLink.__table__
    cols = {c.name for c in table.columns}
    assert cols == {"channel_id", "category"}

    pk_cols = {c.name for c in table.primary_key.columns}
    assert pk_cols == {"channel_id", "category"}
