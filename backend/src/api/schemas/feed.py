from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FeedMedia(BaseModel):
    id: int
    type: Literal["photo", "video", "document"]
    width: int | None
    height: int | None
    duration: int | None


class FeedChannel(BaseModel):
    id: int
    username: str | None
    title: str
    photo_url: str | None


class FeedPost(BaseModel):
    id: int
    tg_message_id: int
    posted_at: datetime
    text: str | None
    text_html: str | None
    views: int | None
    forwards: int | None
    channel: FeedChannel
    media: list[FeedMedia]
    is_saved: bool


class FeedPage(BaseModel):
    posts: list[FeedPost]
    next_cursor: str | None
