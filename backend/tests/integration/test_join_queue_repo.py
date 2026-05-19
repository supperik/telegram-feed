from __future__ import annotations

import pytest
from sqlalchemy import text

from shared.repositories.join_queue import (
    mark_join_failed,
    mark_pending_approval,
    fetch_pending_approval,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mark_pending_approval_sets_status_and_updated_at(db_session, seed_user):
    user_id = await seed_user(tg_user_id=3001)
    qid = (await db_session.execute(
        text("""
            INSERT INTO channel_join_queue (kind, invite_hash, requested_by_user_id, status)
            VALUES ('private_invite', 'abc12345', :u, 'in_progress')
            RETURNING id
        """),
        {"u": user_id},
    )).scalar_one()
    await db_session.commit()

    await mark_pending_approval(db_session, queue_id=qid)
    await db_session.commit()

    row = (await db_session.execute(
        text("SELECT status, updated_at FROM channel_join_queue WHERE id=:id"),
        {"id": qid},
    )).mappings().one()
    assert row["status"] == "pending_approval"
    assert row["updated_at"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mark_join_failed_with_error_code(db_session, seed_user):
    user_id = await seed_user(tg_user_id=3002)
    qid = (await db_session.execute(
        text("""
            INSERT INTO channel_join_queue (kind, invite_hash, requested_by_user_id, status)
            VALUES ('private_invite', 'def67890', :u, 'in_progress')
            RETURNING id
        """),
        {"u": user_id},
    )).scalar_one()
    await db_session.commit()

    await mark_join_failed(
        db_session, queue_id=qid,
        error_code="invite_invalid",
        error_reason="hash bad",
    )
    await db_session.commit()

    row = (await db_session.execute(
        text("SELECT status, error_code, error_reason FROM channel_join_queue WHERE id=:id"),
        {"id": qid},
    )).mappings().one()
    assert row["status"] == "failed"
    assert row["error_code"] == "invite_invalid"
    assert row["error_reason"] == "hash bad"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_pending_approval_returns_rows(db_session, seed_user):
    user_id = await seed_user(tg_user_id=3003)
    await db_session.execute(
        text("""
            INSERT INTO channel_join_queue (kind, invite_hash, requested_by_user_id, status)
            VALUES ('private_invite', 'pa000001', :u, 'pending_approval'),
                   ('private_invite', 'pa000002', :u, 'pending_approval'),
                   ('private_invite', 'donedone', :u, 'done')
        """),
        {"u": user_id},
    )
    await db_session.commit()

    rows = await fetch_pending_approval(db_session)
    hashes = {r.invite_hash for r in rows}
    assert "pa000001" in hashes
    assert "pa000002" in hashes
    assert "donedone" not in hashes
