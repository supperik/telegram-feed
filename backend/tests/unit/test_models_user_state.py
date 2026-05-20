def test_user_source_table():
    from shared.models import UserSource
    pk_cols = [c.name for c in UserSource.__table__.primary_key.columns]
    assert pk_cols == ["user_id", "channel_id"]


def test_user_saved_table():
    from shared.models import UserSavedPost
    pk_cols = [c.name for c in UserSavedPost.__table__.primary_key.columns]
    assert pk_cols == ["user_id", "post_id"]


def test_user_hidden_post_and_channel():
    from shared.models import UserHiddenChannel, UserHiddenPost
    assert {c.name for c in UserHiddenPost.__table__.columns} >= {"user_id", "post_id", "hidden_at"}
    assert {c.name for c in UserHiddenChannel.__table__.columns} >= {
        "user_id",
        "channel_id",
        "hidden_at",
    }


def test_user_read_post_table():
    from shared.models import UserReadPost
    pk_cols = [c.name for c in UserReadPost.__table__.primary_key.columns]
    assert pk_cols == ["user_id", "post_id"]
    assert {c.name for c in UserReadPost.__table__.columns} >= {
        "user_id",
        "post_id",
        "read_at",
    }
