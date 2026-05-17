def test_admin_tables():
    from shared.models import Admin, AdminAction
    assert {"id", "email", "password_hash", "totp_secret", "created_at"} <= \
        {c.name for c in Admin.__table__.columns}
    assert {"id", "admin_id", "action", "target", "created_at"} <= \
        {c.name for c in AdminAction.__table__.columns}


def test_queue_tables():
    from shared.models import ChannelJoinQueue, ChannelSubscription
    assert {"channel_id", "status", "ref_count", "joined_at", "backfilled_at", "last_error"} <= \
        {c.name for c in ChannelSubscription.__table__.columns}
    assert {
        "id",
        "channel_username",
        "requested_by_user_id",
        "status",
        "error_reason",
        "channel_id",
        "created_at",
        "updated_at",
    } <= {c.name for c in ChannelJoinQueue.__table__.columns}
