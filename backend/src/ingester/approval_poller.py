"""Approval poller for pending_approval queue rows.

For each pending_approval row, periodically call CheckChatInviteRequest.
When the admin approves the join, Telegram returns ChatInviteAlready(chat=...)
and we finish the join via _post_join. If the row exceeds timeout_days, mark
it as failed with error_code='approval_timeout'.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from telethon.errors import (
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
)
from telethon.tl.functions.messages import CheckChatInviteRequest
from telethon.tl.types import ChatInviteAlready

from ingester.join_worker import _backfill_channel, _post_join
from shared.repositories.join_queue import fetch_pending_approval, mark_join_failed
from shared.utils.masks import mask_invite_hash

log = structlog.get_logger(__name__)


async def _invoke(client, request):
    """Indirection seam for tests."""
    return await client(request)


async def run_approval_poller(
    client,
    session_factory,
    *,
    minio_client,
    bucket: str,
    poll_interval_s: float = 1800.0,
    timeout_days: int = 7,
) -> None:
    log.info(
        "approval_poller.started",
        poll_interval_s=poll_interval_s,
        timeout_days=timeout_days,
    )
    while True:
        try:
            await _approval_poll_once(
                client, session_factory,
                minio_client=minio_client, bucket=bucket,
                timeout_days=timeout_days,
            )
        except Exception:
            log.exception("approval_poller.iteration_failed")
        await asyncio.sleep(poll_interval_s)


async def _approval_poll_once(
    client,
    session_factory,
    *,
    minio_client,
    bucket: str,
    timeout_days: int,
) -> None:
    async with session_factory() as session:
        rows = await fetch_pending_approval(session)

    for row in rows:
        masked = mask_invite_hash(row.invite_hash)

        # 1) Timeout check
        if _row_age_days(row) >= timeout_days:
            async with session_factory() as session:
                await mark_join_failed(
                    session, queue_id=row.id,
                    error_code="approval_timeout",
                    error_reason=f"pending_approval > {timeout_days}d",
                )
                await session.commit()
            log.info("approval_poller.timed_out", queue_id=row.id, invite_hash=masked)
            continue

        # 2) Re-check invite
        try:
            invite = await _invoke(client, CheckChatInviteRequest(row.invite_hash))
        except (InviteHashInvalidError, InviteHashEmptyError):
            async with session_factory() as session:
                await mark_join_failed(
                    session, queue_id=row.id,
                    error_code="invite_invalid",
                    error_reason="InviteHashInvalid (poller)",
                )
                await session.commit()
            log.warning("approval_poller.invite_invalid", queue_id=row.id, invite_hash=masked)
            continue
        except InviteHashExpiredError:
            async with session_factory() as session:
                await mark_join_failed(
                    session, queue_id=row.id,
                    error_code="invite_expired",
                    error_reason="InviteHashExpired (poller)",
                )
                await session.commit()
            log.warning("approval_poller.invite_expired", queue_id=row.id, invite_hash=masked)
            continue
        except Exception:
            log.exception("approval_poller.check_failed", queue_id=row.id, invite_hash=masked)
            continue

        if isinstance(invite, ChatInviteAlready):
            chat = invite.chat
            async with session_factory() as session:
                channel = await _post_join(session, row=row, chat=chat)
                await session.commit()
            try:
                await _backfill_channel(
                    client, session_factory, minio_client, chat, channel.id,
                    limit=50, bucket=bucket,
                )
            except Exception:
                log.exception("approval_poller.backfill_failed", queue_id=row.id)
            log.info(
                "approval_poller.approved",
                queue_id=row.id, tg_chat_id=int(chat.id), invite_hash=masked,
            )
            continue

        # invite is still ChatInvite preview — nothing to do this tick
        log.debug("approval_poller.still_pending", queue_id=row.id, invite_hash=masked)


def _row_age_days(row) -> float:
    if row.updated_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    delta = now - row.updated_at
    return delta.total_seconds() / 86400.0
