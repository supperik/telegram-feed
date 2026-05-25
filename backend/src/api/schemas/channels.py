from datetime import datetime

from pydantic import BaseModel

from api.schemas.sources import ChannelSummary


class CatalogChannelItem(BaseModel):
    channel: ChannelSummary
    subscribers_count: int
    last_post_at: datetime | None
    is_subscribed: bool
    is_hidden_from_catalog: bool
    categories: list[str] = []


class CatalogPage(BaseModel):
    items: list[CatalogChannelItem]
    next_cursor: str | None = None


class ChannelCategory(BaseModel):
    slug: str
    title: str


class ChannelCategoriesResponse(BaseModel):
    categories: list[ChannelCategory]
