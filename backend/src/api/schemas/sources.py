from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AddSourceIn(BaseModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_]+$")


class ChannelSummary(BaseModel):
    id: int
    username: str | None
    title: str
    photo_url: str | None


class AddSourceOut(BaseModel):
    status: Literal["subscribed", "queued"]
    channel: ChannelSummary | None
    queue_id: int | None = None


class SourceListItem(BaseModel):
    channel: ChannelSummary
    added_at: datetime
    subscription_status: str | None


class QueueStatusOut(BaseModel):
    queue_id: int
    status: Literal["pending", "in_progress", "done", "failed"]
    error_reason: str | None
    channel: ChannelSummary | None


class SourceList(BaseModel):
    items: list[SourceListItem]
