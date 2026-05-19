"""One-shot backfill: refetch posts whose text_html IS NULL and recompute
it from the live Telegram message entities.

Idempotent: after a successful pass the targets query returns nothing,
so re-running is a no-op.

For messages that have been deleted in Telegram (get_messages returns
None for that id), the stored plain `text` is HTML-escaped and used as
text_html so the post stays readable, just without inline formatting.

Usage:
    poetry run python -m scripts.backfill_text_html
"""
from __future__ import annotations

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from ingester.text_html import entities_to_html
from shared.models import Channel, ChannelSubscription, Post

log = structlog.get_logger(__name__)

_BATCH_SIZE = 100


async def backfill_text_html(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Recompute text_html for every post that has plain text but no HTML.

    Returns the number of posts whose text_html was set.
    """
    async with session_factory() as session:
        res = await session.execute(
            select(Post.id, Post.tg_message_id, Channel.tg_chat_id, Post.text)
            .join(Channel, Channel.id == Post.channel_id)
            .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
            .where(
                Post.text.isnot(None),
                Post.text_html.is_(None),
                ChannelSubscription.status == "active",
            )
        )
        rows = res.all()

    if not rows:
        log.info("backfill_text_html.noop")
        return 0

    by_channel: dict[int, list[tuple[int, int, str]]] = {}
    for post_id, tg_message_id, tg_chat_id, text in rows:
        by_channel.setdefault(tg_chat_id, []).append((post_id, tg_message_id, text))

    log.info("backfill_text_html.start", channels=len(by_channel), posts=len(rows))

    total = 0
    for tg_chat_id, posts in by_channel.items():
        try:
            entity = await client.get_entity(tg_chat_id)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "backfill_text_html.get_entity_failed",
                tg_chat_id=tg_chat_id,
                error=str(e),
            )
            continue

        # text lookup by tg_message_id for fallback (deleted messages).
        text_by_msg_id = {tg_msg_id: text for _, tg_msg_id, text in posts}
        post_id_by_msg_id = {tg_msg_id: post_id for post_id, tg_msg_id, _ in posts}

        msg_ids = [tg_msg_id for _, tg_msg_id, _ in posts]
        for batch_start in range(0, len(msg_ids), _BATCH_SIZE):
            batch = msg_ids[batch_start : batch_start + _BATCH_SIZE]
            try:
                messages = await client.get_messages(entity, ids=batch)
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "backfill_text_html.get_messages_failed",
                    tg_chat_id=tg_chat_id,
                    error=str(e),
                )
                continue

            for tg_msg_id, msg in zip(batch, messages):
                post_id = post_id_by_msg_id[tg_msg_id]
                stored_text = text_by_msg_id[tg_msg_id]
                if msg is None:
                    text_html = _escape_only(stored_text)
                else:
                    msg_text = getattr(msg, "message", None) or getattr(msg, "text", None) or stored_text
                    text_html = entities_to_html(msg_text, getattr(msg, "entities", None))
                if text_html is None:
                    continue

                async with session_factory() as session:
                    await session.execute(
                        update(Post).where(Post.id == post_id).values(text_html=text_html)
                    )
                    await session.commit()
                total += 1

    log.info("backfill_text_html.complete", filled=total)
    return total


def _escape_only(text: str | None) -> str | None:
    if text is None:
        return None
    return entities_to_html(text, None)


async def _run_from_cli() -> None:  # pragma: no cover
    """Entrypoint for scripts/backfill_text_html.py."""
    from shared.config import get_settings
    from shared.db import make_engine, make_session_factory
    from shared.logging import configure_logging
    from shared.tg.client_factory import make_client
    from ingester.session import default_sessions_dir

    configure_logging()
    settings = get_settings()
    if not settings.tg_api_id or not settings.tg_api_hash:
        raise SystemExit("TG_API_ID/TG_API_HASH not configured")

    client = make_client(settings, sessions_dir=default_sessions_dir())
    await client.start(phone=settings.tg_phone)
    engine = make_engine(settings.postgres_dsn)
    session_factory = make_session_factory(engine)
    try:
        n = await backfill_text_html(client, session_factory)
        print(f"backfill_text_html: filled {n} posts")  # noqa: T201
    finally:
        await client.disconnect()
        await engine.dispose()


