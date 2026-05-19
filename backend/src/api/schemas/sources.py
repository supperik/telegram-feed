from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class AddSourceIn(BaseModel):
    input: str = Field(min_length=1, max_length=256)


class ChannelSummary(BaseModel):
    id: int
    username: str | None
    title: str
    photo_url: str | None = None

    @computed_field  # type: ignore[misc]
    @property
    def is_private(self) -> bool:
        return self.username is None


class AddSourceOut(BaseModel):
    status: Literal["subscribed", "queued"]
    channel: ChannelSummary | None
    queue_id: int | None = None


class SourceListItem(BaseModel):
    channel: ChannelSummary
    added_at: datetime
    subscription_status: str | None


QueueStatusValue = Literal["pending", "in_progress", "pending_approval", "done", "failed"]


class QueueStatusOut(BaseModel):
    queue_id: int
    status: QueueStatusValue
    error_code: str | None = None
    error_reason: str | None = None
    channel: ChannelSummary | None = None


class SourceList(BaseModel):
    items: list[SourceListItem]


class HiddenSourceItem(BaseModel):
    channel: ChannelSummary
    hidden_at: datetime


class HiddenSourceList(BaseModel):
    items: list[HiddenSourceItem]
