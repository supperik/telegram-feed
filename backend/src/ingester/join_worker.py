import asyncio
from datetime import datetime, timezone

import structlog
from minio import Minio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    ChannelsTooMuchError,
    FloodWaitError,
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    InviteRequestSentError,
    UserAlreadyParticipantError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import (
    CheckChatInviteRequest,
    ImportChatInviteRequest,
)
from telethon.tl.types import ChatInviteAlready

from ingester.normalize import normalize_message
from shared.models import ChannelSubscription
from shared.repositories.channels import upsert_channel
from shared.repositories.join_queue import (
    mark_join_done,
    mark_join_failed,
    mark_pending_approval,
    pop_pending_join_request,
)
from shared.repositories.posts import upsert_post
from shared.repositories.user_sources import add_user_source
from shared.utils.masks import mask_invite_hash

log = structlog.get_logger(__name__)


async def _invoke(client, request):
    """Indirection seam for tests: tests monkeypatch jw._invoke to control the
    Telethon call sequence without standing up a real client.
    """
    return await client(request)


async def _backfill_channel(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    minio_client: Minio,
    entity,
    channel_id: int,
    *,
    limit: int,
    bucket: str,
) -> None:
    """Fetch the most recent `limit` messages from `entity` and upsert each.

    NOTE: P4 keeps backfill simple — no photo download in backfill yet,
    only live and catchup download. This is a tradeoff: backfill stays fast
    at the cost of older posts initially having no thumbnails. Live ingest
    downloads everything going forward.
    """
    async for msg in client.iter_messages(entity, limit=limit):
        post_values, media_values = normalize_message(msg, channel_id)
        async with session_factory() as session:
            await upsert_post(session, post_values, media_values)
            await session.commit()

    # After backfill, mark subscription active.
    async with session_factory() as session:
        await session.execute(
            update(ChannelSubscription)
            .where(ChannelSubscription.channel_id == channel_id)
            .values(status="active", backfilled_at=datetime.now(tz=timezone.utc))
        )
        await session.commit()


async def _post_join(session, *, row, chat):
    """Common tail of any successful join: upsert channel, link user_source, mark done.

    Used by both public-username flow and (T7) private-invite flow. Returns the
    Channel ORM object so callers can run backfill outside the session block
    (Telethon Channel from chat object is passed in separately and not stored).
    """
    channel = await upsert_channel(
        session,
        tg_chat_id=int(chat.id),
        username=getattr(chat, "username", None),
        title=getattr(chat, "title", None) or getattr(chat, "username", None) or "(no title)",
    )
    await add_user_source(
        session, user_id=row.requested_by_user_id, channel_id=channel.id
    )
    await mark_join_done(session, queue_id=row.id, channel_id=channel.id)
    return channel


async def _join_private(client, session_factory, *, row):
    """Telethon flow for `kind == 'private_invite'` queue rows.

    Two-step dance with CheckChatInviteRequest -> ImportChatInviteRequest:
    - If the bot is already a member, Check returns ChatInviteAlready
      and we skip Import entirely.
    - If approval is required, Import raises InviteRequestSentError and
      we park the row in `pending_approval` (T8 reaper finalises).
    - Otherwise we extract the new Channel from Updates.chats[0].

    On success returns `(chat, channel_id)` so the caller can run backfill
    outside the session block; on every error / approval path returns None
    after committing the appropriate queue row update.
    """
    masked = mask_invite_hash(row.invite_hash)
    try:
        invite = await _invoke(client, CheckChatInviteRequest(row.invite_hash))
    except (InviteHashInvalidError, InviteHashEmptyError):
        async with session_factory() as session:
            await mark_join_failed(
                session,
                queue_id=row.id,
                error_code="invite_invalid",
                error_reason="InviteHashInvalid",
            )
            await session.commit()
        log.warning("join_worker.invite_invalid", queue_id=row.id, invite_hash=masked)
        return None
    except InviteHashExpiredError:
        async with session_factory() as session:
            await mark_join_failed(
                session,
                queue_id=row.id,
                error_code="invite_expired",
                error_reason="InviteHashExpired",
            )
            await session.commit()
        log.warning("join_worker.invite_expired", queue_id=row.id, invite_hash=masked)
        return None

    if isinstance(invite, ChatInviteAlready):
        async with session_factory() as session:
            channel = await _post_join(session, row=row, chat=invite.chat)
            await session.commit()
            channel_id = channel.id
        log.info(
            "join_worker.private_already_member",
            queue_id=row.id,
            tg_chat_id=int(invite.chat.id),
            invite_hash=masked,
        )
        return invite.chat, channel_id

    # invite is ChatInvite (preview) — try to import; may raise
    # InviteRequestSentError when the channel requires owner approval.
    try:
        updates = await _invoke(client, ImportChatInviteRequest(row.invite_hash))
    except InviteRequestSentError:
        async with session_factory() as session:
            await mark_pending_approval(session, queue_id=row.id)
            await session.commit()
        log.info(
            "join_worker.private_pending_approval",
            queue_id=row.id,
            invite_hash=masked,
        )
        return None
    except ChannelsTooMuchError:
        async with session_factory() as session:
            await mark_join_failed(
                session,
                queue_id=row.id,
                error_code="channels_too_much",
                error_reason="ChannelsTooMuch",
            )
            await session.commit()
        log.warning("join_worker.channels_too_much", queue_id=row.id, invite_hash=masked)
        return None
    except FloodWaitError as exc:
        async with session_factory() as session:
            await mark_join_failed(
                session,
                queue_id=row.id,
                error_code="flood_wait",
                error_reason=f"FloodWait({getattr(exc, 'seconds', None)}s)",
            )
            await session.commit()
        log.warning(
            "join_worker.flood_wait",
            queue_id=row.id,
            invite_hash=masked,
            seconds=getattr(exc, "seconds", None),
        )
        return None
    except UserAlreadyParticipantError:
        # Race: another worker / our own retry already joined between Check
        # and Import. Re-Check should now return ChatInviteAlready.
        try:
            invite2 = await _invoke(client, CheckChatInviteRequest(row.invite_hash))
        except Exception:  # noqa: BLE001 — degrade to "unknown" if re-check fails
            invite2 = None
        if isinstance(invite2, ChatInviteAlready):
            async with session_factory() as session:
                channel = await _post_join(session, row=row, chat=invite2.chat)
                await session.commit()
                channel_id = channel.id
            log.info(
                "join_worker.private_joined_race",
                queue_id=row.id,
                tg_chat_id=int(invite2.chat.id),
                invite_hash=masked,
            )
            return invite2.chat, channel_id
        async with session_factory() as session:
            await mark_join_failed(
                session,
                queue_id=row.id,
                error_code="unknown",
                error_reason="UserAlreadyParticipant_no_recheck",
            )
            await session.commit()
        return None

    chats = getattr(updates, "chats", None)
    if not chats:
        async with session_factory() as session:
            await mark_join_failed(
                session,
                queue_id=row.id,
                error_code="unknown",
                error_reason="Updates_no_chats",
            )
            await session.commit()
        log.warning("join_worker.no_chats_in_updates", queue_id=row.id, invite_hash=masked)
        return None
    chat = chats[0]
    async with session_factory() as session:
        channel = await _post_join(session, row=row, chat=chat)
        await session.commit()
        channel_id = channel.id
    log.info(
        "join_worker.private_joined",
        queue_id=row.id,
        tg_chat_id=int(chat.id),
        invite_hash=masked,
    )
    return chat, channel_id


async def _handle_one_pending(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
) -> None:
    """Pop one pending join, attempt it, commit the outcome. No-op if empty."""
    async with session_factory() as session:
        pending = await pop_pending_join_request(session)
        if pending is None:
            await session.commit()
            return
        # Commit the in_progress claim so the row is visible / locked-as-taken
        # across the network round-trip. _join_private opens its own sessions
        # so it must not share this one anyway.
        await session.commit()
        # Detach: we use only attribute snapshots from `pending` below.
        pending_kind = pending.kind
        pending_id = pending.id
        username = pending.channel_username

    # Private-invite branch: hand off entirely to _join_private (manages
    # its own session lifecycle + mark_done/mark_failed/mark_pending_approval).
    if pending_kind == "private_invite":
        outcome = await _join_private(client, session_factory, row=pending)
        if outcome is None:
            return  # already logged + marked
        chat, channel_id = outcome
        await _backfill_channel(
            client, session_factory, minio_client, chat, channel_id,
            limit=50, bucket=bucket,
        )
        return

    # Public-username branch (existing behaviour).
    async with session_factory() as session:
        queue_id = pending_id
        try:
            entity = await client.get_entity(username)
        except UsernameNotOccupiedError:
            await mark_join_failed(
                session,
                queue_id=queue_id,
                error_code="username_not_occupied",
                error_reason="username_not_occupied",
            )
            await session.commit()
            log.warning("join_worker.username_not_occupied", username=username, queue_id=queue_id)
            return
        except UsernameInvalidError:
            await mark_join_failed(
                session,
                queue_id=queue_id,
                error_code="username_invalid",
                error_reason="username_invalid",
            )
            await session.commit()
            log.warning("join_worker.username_invalid", username=username, queue_id=queue_id)
            return
        except ChannelPrivateError:
            await mark_join_failed(
                session,
                queue_id=queue_id,
                error_code="channel_private",
                error_reason="channel_private",
            )
            await session.commit()
            log.warning("join_worker.channel_private", username=username, queue_id=queue_id)
            return
        except FloodWaitError as e:
            await session.rollback()  # let the row revert to pending? actually no — it's already in_progress.
            # Sleep and let the next loop iteration retry (the in_progress row stays as-is).
            log.info("join_worker.flood_wait", seconds=e.seconds, queue_id=queue_id)
            await asyncio.sleep(e.seconds + 1)
            return

        try:
            await client(JoinChannelRequest(entity))
        except FloodWaitError as e:
            await session.rollback()
            log.info("join_worker.flood_wait_on_join", seconds=e.seconds, queue_id=queue_id)
            await asyncio.sleep(e.seconds + 1)
            return
        except Exception as e:  # noqa: BLE001 — keep loop alive
            await mark_join_failed(
                session,
                queue_id=queue_id,
                error_code="unknown",
                error_reason=f"join_failed:{type(e).__name__}",
            )
            await session.commit()
            log.error("join_worker.join_failed", username=username, error=str(e))
            return

        # Common tail (upsert channel + link user_source + mark done) is
        # extracted into _post_join so the private-invite flow (T7) can share it.
        # add_user_source bumps ref_count internally for new links, so we don't
        # call increment_ref_count separately here.
        channel = await _post_join(session, row=pending, chat=entity)
        await session.commit()
        log.info(
            "join_worker.joined",
            channel_id=channel.id,
            tg_chat_id=channel.tg_chat_id,
            username=username,
        )

    # Backfill happens outside the join session — it owns its own sessions.
    await _backfill_channel(
        client, session_factory, minio_client, entity, channel.id,
        limit=50, bucket=bucket,
    )


async def run_join_worker(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
    poll_interval_s: float = 2.0,
) -> None:
    log.info("join_worker.started", poll_interval_s=poll_interval_s)
    while True:
        try:
            await _handle_one_pending(
                client, session_factory,
                minio_client=minio_client, bucket=bucket,
            )
        except Exception as e:  # noqa: BLE001 — keep loop alive
            log.exception("join_worker.loop_error", error=str(e))
        await asyncio.sleep(poll_interval_s)
