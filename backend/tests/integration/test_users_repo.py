import pytest

from shared.repositories.users import upsert_user_by_tg_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_inserts_then_updates(db_session) -> None:
    u1 = await upsert_user_by_tg_id(
        db_session, tg_user_id=42, tg_username="ada", tg_first_name="Ada", tg_photo_url=None
    )
    await db_session.commit()
    assert u1.tg_user_id == 42

    u2 = await upsert_user_by_tg_id(
        db_session, tg_user_id=42, tg_username="ada_l", tg_first_name="Ada L.", tg_photo_url="u"
    )
    await db_session.commit()
    assert u2.id == u1.id
    assert u2.tg_username == "ada_l"
    assert u2.tg_first_name == "Ada L."
    assert u2.tg_photo_url == "u"
