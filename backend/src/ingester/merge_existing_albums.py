"""One-shot merge: collapse Post-rows that were ingested as separate
messages but actually belong to one Telegram media group.

Algorithm: for every Post in the DB with ``tg_grouped_id IS NULL``,
ask Telegram what the message's grouped_id is (via get_messages).
Posts with the same (channel_id, grouped_id) are folded:

- The head post (lowest tg_message_id) keeps its row and is tagged
  with the grouped_id. Its existing Media rows stay in place.
- Every tail post has its Media reassigned to the head, with positions
  continuing from the head's current max(position) + 1.
- Tail Post-rows are DELETEd.

Idempotent: once every Post has tg_grouped_id (NULL or otherwise), the
targets query returns zero rows.

Designed to run once after the migration that adds Post.tg_grouped_id
ships to production; safe to keep wired into the ingester boot path.
"""
from __future__ import annotations

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient
from telethon.tl.types import PeerChannel

from shared.models import Channel, ChannelSubscription, Media, Post

log = structlog.get_logger(__name__)

_BATCH = 100


async def merge_existing_albums(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Merge sibling Post-rows that belong to the same Telegram media
    group into a single Post. Returns the count of Post-rows deleted
    (i.e. the number of merge-aways)."""
    async with session_factory() as session:
        res = await session.execute(
            select(
                Post.id,
                Post.tg_message_id,
                Channel.id.label("channel_id"),
                Channel.tg_chat_id,
            )
            .join(Channel, Channel.id == Post.channel_id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(
                Post.tg_grouped_id.is_(None),
                ChannelSubscription.status == "active",
            )
        )
        rows = res.all()

    if not rows:
        log.info("merge_existing_albums.noop")
        return 0

    by_channel: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for post_id, tg_message_id, channel_id, tg_chat_id in rows:
        by_channel.setdefault((channel_id, tg_chat_id), []).append(
            (post_id, tg_message_id)
        )

    log.info("merge_existing_albums.start", channels=len(by_channel), posts=len(rows))

    total_merged = 0
    for (channel_id, tg_chat_id), post_pairs in by_channel.items():
        try:
            # PeerChannel for unambiguous resolution after a cold restart; see 7h6.
            entity = await client.get_entity(PeerChannel(tg_chat_id))
        except Exception as e:  # noqa: BLE001
            log.warning(
                "merge_existing_albums.get_entity_failed",
                channel_id=channel_id,
                error=str(e),
            )
            continue

        msg_by_id: dict[int, object] = {}
        msg_ids = [p[1] for p in post_pairs]
        for i in range(0, len(msg_ids), _BATCH):
            batch = msg_ids[i : i + _BATCH]
            try:
                messages = await client.get_messages(entity, ids=batch)
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "merge_existing_albums.get_messages_failed",
                    channel_id=channel_id,
                    error=str(e),
                )
                continue
            for mid, msg in zip(batch, messages):
                if msg is not None:
                    msg_by_id[mid] = msg

        groups: dict[int, list[tuple[int, int]]] = {}
        for post_id, tg_message_id in post_pairs:
            msg = msg_by_id.get(tg_message_id)
            if msg is None:
                continue
            gid = getattr(msg, "grouped_id", None)
            if gid is None:
                continue
            groups.setdefault(int(gid), []).append((post_id, tg_message_id))

        for gid, members in groups.items():
            members.sort(key=lambda p: p[1])
            if len(members) == 1:
                # Solo sibling — just tag with grouped_id so future siblings
                # (if they ever arrive) attach to it.
                only_post_id = members[0][0]
                async with session_factory() as session:
                    await session.execute(
                        update(Post)
                        .where(Post.id == only_post_id)
                        .values(tg_grouped_id=gid)
                    )
                    await session.commit()
                total_merged += 1
                continue

            head_post_id = members[0][0]
            tail_ids = [m[0] for m in members[1:]]

            async with session_factory() as session:
                max_pos_res = await session.execute(
                    select(func.coalesce(func.max(Media.position), -1)).where(
                        Media.post_id == head_post_id
                    )
                )
                next_pos = int(max_pos_res.scalar_one()) + 1

                # Track tg_file_ids already living on the head — moving a tail
                # media row whose tg_file_id is already there would violate the
                # UNIQUE(post_id, tg_file_id) index added in 0007.
                head_files_res = await session.execute(
                    select(Media.tg_file_id).where(Media.post_id == head_post_id)
                )
                present_files: set[str | None] = set(head_files_res.scalars().all())

                for tail_post_id in tail_ids:
                    tail_media_res = await session.execute(
                        select(Media.id, Media.tg_file_id)
                        .where(Media.post_id == tail_post_id)
                        .order_by(Media.id.asc())
                    )
                    for media_id, tg_file_id in tail_media_res.all():
                        if tg_file_id in present_files:
                            await session.execute(
                                delete(Media).where(Media.id == media_id)
                            )
                            continue
                        await session.execute(
                            update(Media)
                            .where(Media.id == media_id)
                            .values(post_id=head_post_id, position=next_pos)
                        )
                        present_files.add(tg_file_id)
                        next_pos += 1

                await session.execute(
                    delete(Post).where(Post.id.in_(tail_ids))
                )
                await session.execute(
                    update(Post)
                    .where(Post.id == head_post_id)
                    .values(tg_grouped_id=gid)
                )
                await session.commit()

            total_merged += len(tail_ids)

    log.info("merge_existing_albums.complete", merged=total_merged)
    return total_merged


async def _run_from_cli() -> None:  # pragma: no cover
    from ingester.session import default_sessions_dir
    from shared.config import get_settings
    from shared.db import make_engine, make_session_factory
    from shared.logging import configure_logging
    from shared.tg.client_factory import make_client

    configure_logging()
    settings = get_settings()
    if not settings.tg_api_id or not settings.tg_api_hash:
        raise SystemExit("TG_API_ID/TG_API_HASH not configured")

    client = make_client(settings, sessions_dir=default_sessions_dir())
    await client.start(phone=settings.tg_phone)
    engine = make_engine(settings.postgres_dsn)
    session_factory = make_session_factory(engine)
    try:
        n = await merge_existing_albums(client, session_factory)
        print(f"merge_existing_albums: merged-away {n} posts")  # noqa: T201
    finally:
        await client.disconnect()
        await engine.dispose()
