from api.schemas.channels import CatalogChannelItem, CatalogPage
from api.schemas.sources import ChannelSummary


def test_catalog_channel_item_serialises() -> None:
    item = CatalogChannelItem(
        channel=ChannelSummary(id=1, username="x", title="X", photo_url=None),
        subscribers_count=3,
        last_post_at=None,
        is_subscribed=False,
        is_hidden_from_catalog=False,
    )
    data = item.model_dump()
    assert data["channel"]["is_private"] is False  # computed field on ChannelSummary
    assert data["subscribers_count"] == 3


def test_catalog_page_default_next_cursor_none() -> None:
    page = CatalogPage(items=[])
    assert page.next_cursor is None
