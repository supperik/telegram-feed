from sqlalchemy import BigInteger, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    tg_file_id: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    video_storage_key: Mapped[str | None] = mapped_column(String(1024))
