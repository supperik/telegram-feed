from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func  # noqa: F401
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    photo_storage_key: Mapped[str | None] = mapped_column(String(1024))
    posts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    banned_reason: Mapped[str | None] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invite_hash: Mapped[str | None] = mapped_column(String(128))


class ChannelBackfillState(Base):
    """Per-channel lazy-history-backfill cursor + TTL lock.

    `locked_until` doubles as a flood-wait backoff / round-robin "next
    eligible at" timestamp — see the design doc.
    """
    __tablename__ = "channel_backfill_state"

    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    fully_backfilled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    oldest_seen_msg_id: Mapped[int | None] = mapped_column(Integer)
    last_backfill_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelCategoryLink(Base):
    __tablename__ = "channel_categories"

    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
