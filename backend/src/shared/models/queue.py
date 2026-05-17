from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class ChannelSubscription(Base):
    __tablename__ = "channel_subscriptions"

    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("channels.id"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelJoinQueue(Base):
    __tablename__ = "channel_join_queue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_username: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_reason: Mapped[str | None] = mapped_column(Text)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("channels.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
