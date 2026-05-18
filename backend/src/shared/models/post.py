from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("channel_id", "tg_message_id", name="uq_posts_channel_id_tg_message_id"),
        Index("ix_posts_channel_id_posted_at", "channel_id", "posted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id"), nullable=False)
    tg_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tg_grouped_id: Mapped[int | None] = mapped_column(BigInteger)
    text: Mapped[str | None] = mapped_column(Text)
    text_html: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    views: Mapped[int | None] = mapped_column(Integer)
    forwards: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
