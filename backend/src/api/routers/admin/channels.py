from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.channel_photo import channel_photo_url
from api.deps import get_current_admin, get_db
from shared.models import Admin
from shared.repositories.admins import (
    ban_channel,
    get_channel_or_none,
    get_channel_row_for_admin,
    list_channels_for_admin,
    unban_channel,
)
from shared.repositories.audit import append_admin_action


router = APIRouter(prefix="/admin/channels", tags=["admin"])


class ChannelOut(BaseModel):
    id: int
    tg_chat_id: int
    username: str | None
    title: str
    description: str | None
    photo_url: str | None
    posts_count: int
    ref_count: int
    banned: bool
    banned_reason: str | None
    last_post_at: datetime | None
    created_at: datetime


class ChannelsListResponse(BaseModel):
    channels: list[ChannelOut]
    next_cursor: str | None


class BanRequest(BaseModel):
    reason: str


class UnbanRequest(BaseModel):
    pass


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "channel_not_found"}},
    )


@router.get("", response_model=ChannelsListResponse)
async def list_channels(
    cursor: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ChannelsListResponse:
    rows, next_cursor = await list_channels_for_admin(db, q=q, cursor=cursor, limit=limit)
    return ChannelsListResponse(
        channels=[_channel_out_from_row(r) for r in rows],
        next_cursor=next_cursor,
    )


def _channel_out_from_row(r: dict) -> "ChannelOut":
    return ChannelOut(
        id=r["id"],
        tg_chat_id=r["tg_chat_id"],
        username=r["username"],
        title=r["title"],
        description=r["description"],
        photo_url=channel_photo_url(r["id"], r["photo_storage_key"]),
        posts_count=r["posts_count"],
        ref_count=r["ref_count"],
        banned=r["banned"],
        banned_reason=r["banned_reason"],
        last_post_at=r["last_post_at"],
        created_at=r["created_at"],
    )


@router.post("/{channel_id}/ban", response_model=ChannelOut)
async def ban_channel_endpoint(
    channel_id: int,
    body: BanRequest,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ChannelOut:
    existing = await get_channel_or_none(db, channel_id)
    if existing is None:
        raise _not_found()
    updated = await ban_channel(db, channel_id, body.reason)
    if updated is None:
        raise _not_found()
    await append_admin_action(
        db, admin_id=admin.id,
        action="ban_channel",
        target={"channel_id": channel_id, "reason": body.reason},
    )
    await db.commit()
    row = await get_channel_row_for_admin(db, channel_id)
    if row is None:
        raise _not_found()
    return _channel_out_from_row(row)


@router.post("/{channel_id}/unban", response_model=ChannelOut)
async def unban_channel_endpoint(
    channel_id: int,
    body: UnbanRequest | None = None,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ChannelOut:
    existing = await get_channel_or_none(db, channel_id)
    if existing is None:
        raise _not_found()
    updated = await unban_channel(db, channel_id)
    if updated is None:
        raise _not_found()
    await append_admin_action(
        db, admin_id=admin.id,
        action="unban_channel",
        target={"channel_id": channel_id},
    )
    await db.commit()
    row = await get_channel_row_for_admin(db, channel_id)
    if row is None:
        raise _not_found()
    return _channel_out_from_row(row)
