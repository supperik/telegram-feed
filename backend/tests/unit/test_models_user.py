def test_user_columns():
    from shared.models import User
    cols = {c.name for c in User.__table__.columns}
    assert {"id", "tg_user_id", "tg_username", "tg_first_name",
            "tg_photo_url", "created_at", "last_seen_at"} <= cols
    assert User.__table__.c.tg_user_id.unique is True
