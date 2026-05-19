import asyncio
from datetime import datetime, timezone

import structlog
from minio import Minio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
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

from ingester.live import (
    _download_one_and_update_storage_key,
    _to_marked_chat_id,
    download_and_set_storage_keys,
)
from ingester.normalize import normalize_album, normalize_message
from ingester.photos import download_and_store_channel_photo
from shared.models import Channel, ChannelSubscription
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
    settings,
) -> None:
    """Fetch the most recent `limit` messages from `entity`, upsert each, and
    download its media.

    Groups consecutive media-group messages into a single Post with N Media
    rows, then downloads photos / video-thumbs and writes storage_key. Mirrors
    catchup_channels (live.py) so freshly joined channels show thumbnails
    immediately instead of waiting for the next ingester boot to run
    backfill_recent_media.
    """
    collected = []
    async for msg in client.iter_messages(entity, limit=limit):
        collected.append(msg)

    albums: dict[int, list] = {}
    solos: list = []
    for m in collected:
        gid = getattr(m, "grouped_id", None)
        if gid is not None:
            albums.setdefault(int(gid), []).append(m)
        else:
            solos.append(m)

    for msgs in albums.values():
        post_values, media_values = normalize_album(msgs, channel_id)
        async with session_factory() as session:
            new_id = await upsert_post(session, post_values, media_values)
            if new_id is not None:
                ordered = sorted(msgs, key=lambda mm: int(mm.id))
                for media, msg in zip(media_values, ordered):
                    await _download_one_and_update_storage_key(
                        session, msg=msg, channel_id=channel_id,
                        post_id=new_id, media=media,
                        client=client, minio_client=minio_client, bucket=bucket,
                        settings=settings,
                    )
            await session.commit()

    for msg in solos:
        post_values, media_values = normalize_message(msg, channel_id)
        async with session_factory() as session:
            new_id = await upsert_post(session, post_values, media_values)
            if new_id is not None:
                await download_and_set_storage_keys(
                    session, msg=msg, channel_id=channel_id,
                    new_post_id=new_id, media_values=media_values,
                    client=client, minio_client=minio_client, bucket=bucket,
                    settings=settings,
                )
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
    settings,
    chat_map: dict[int, int] | None = None,
) -> None:
    """Pop one pending join, attempt it, commit the outcome. No-op if empty.

    On successful join, when `chat_map` is provided, the new channel is
    registered in it under its marked peer-id. This lets the live
    NewMessage handler (see ingester.live.subscribe_to_active_channels)
    pick up the new channel immediately, without an ingester restart
    (telegram-feed-3bv).
    """
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
        if chat_map is not None:
            chat_map[_to_marked_chat_id(int(chat.id))] = channel_id
        await _backfill_channel(
            client, session_factory, minio_client, chat, channel_id,
            limit=50, bucket=bucket, settings=settings,
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
        if chat_map is not None:
            chat_map[_to_marked_chat_id(int(entity.id))] = channel.id
        log.info(
            "join_worker.joined",
            channel_id=channel.id,
            tg_chat_id=channel.tg_chat_id,
            username=username,
        )

    # Best-effort: download the channel avatar and store its key. Failures
    # here must never break the join — the channel still works without a
    # cached avatar, and `backfill_channel_photos` retries on boot.
    try:
        storage_key = await download_and_store_channel_photo(
            client, minio_client, entity,
            channel_id=channel.id, bucket=bucket,
        )
    except Exception as e:  # noqa: BLE001
        try:
            log.warning("join_worker.channel_photo_failed",
                        channel_id=channel.id, error=str(e))
        except ValueError:
            pass
        storage_key = None
    if storage_key is not None:
        async with session_factory() as session:
            await session.execute(
                update(Channel)
                .where(Channel.id == channel.id)
                .values(photo_storage_key=storage_key)
            )
            await session.commit()

    # Backfill happens outside the join session — it owns its own sessions.
    await _backfill_channel(
        client, session_factory, minio_client, entity, channel.id,
        limit=50, bucket=bucket, settings=settings,
    )


async def run_join_worker(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    minio_client: Minio,
    bucket: str,
    settings,
    chat_map: dict[int, int] | None = None,
    poll_interval_s: float = 2.0,
) -> None:
    log.info("join_worker.started", poll_interval_s=poll_interval_s)
    while True:
        try:
            await _handle_one_pending(
                client, session_factory,
                minio_client=minio_client, bucket=bucket,
                settings=settings,
                chat_map=chat_map,
            )
        except Exception as e:  # noqa: BLE001 — keep loop alive
            log.exception("join_worker.loop_error", error=str(e))
        await asyncio.sleep(poll_interval_s)
