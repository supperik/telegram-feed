from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeedMedia(BaseModel):
    id: int
    type: Literal["photo", "video", "document"]
    width: int | None
    height: int | None
    duration: int | None
    has_video_file: bool = False


class FeedChannel(BaseModel):
    id: int
    tg_chat_id: int
    username: str | None
    title: str
    photo_url: str | None
    invite_url: str | None = None


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


class ReadRequest(BaseModel):
    post_ids: list[int] = Field(max_length=200)


class ReadResponse(BaseModel):
    marked: int
