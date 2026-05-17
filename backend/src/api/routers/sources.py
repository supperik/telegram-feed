from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.errors import APIError
from api.schemas.sources import (
    AddSourceIn,
    AddSourceOut,
    ChannelSummary,
    QueueStatusOut,
    SourceList,
    SourceListItem,
)
from shared.models import Channel, ChannelJoinQueue, User
from shared.repositories.user_sources import (
    add_user_source,
    list_user_sources,
    remove_user_source,
)
from shared.repositories.user_states import hide_channel as hide_channel_repo

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post(
    "",
    response_model=None,
    responses={
        200: {"model": AddSourceOut},
        202: {"model": AddSourceOut},
    },
)
async def add_source(
    body: AddSourceIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AddSourceOut | JSONResponse:
    username = body.username.lower()
    res = await db.execute(select(Channel).where(Channel.username == username))
    ch = res.scalar_one_or_none()
    if ch is not None:
        if ch.banned:
            raise APIError(code="channel_banned", message="Channel is banned", status_code=403)
        await add_user_source(db, user_id=user.id, channel_id=ch.id)
        await db.commit()
        return AddSourceOut(
            status="subscribed",
            channel=ChannelSummary(
                id=ch.id, username=ch.username, title=ch.title, photo_url=ch.photo_url
            ),
        )

    queue_row = ChannelJoinQueue(
        channel_username=username,
        requested_by_user_id=user.id,
        status="pending",
    )
    db.add(queue_row)
    await db.commit()
    await db.refresh(queue_row)
    return JSONResponse(
        status_code=202,
        content={"status": "queued", "channel": None, "queue_id": queue_row.id},
    )


@router.get("", response_model=SourceList)
async def list_sources(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SourceList:
    rows = await list_user_sources(db, user_id=user.id)
    return SourceList(
        items=[
            SourceListItem(
                channel=ChannelSummary(
                    id=row.channel_id,
                    username=row.channel_username,
                    title=row.channel_title,
                    photo_url=row.channel_photo_url,
                ),
                added_at=row.added_at,
                subscription_status=row.subscription_status,
            )
            for row in rows
        ]
    )


@router.get("/queue/{queue_id}", response_model=QueueStatusOut)
async def queue_status(
    queue_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueueStatusOut:
    qrow = await db.get(ChannelJoinQueue, queue_id)
    if qrow is None or qrow.requested_by_user_id != user.id:
        raise APIError(code="queue_not_found", message="Queue entry not found", status_code=404)
    channel = None
    if qrow.channel_id is not None:
        ch = await db.get(Channel, qrow.channel_id)
        if ch is not None:
            channel = ChannelSummary(
                id=ch.id, username=ch.username, title=ch.title, photo_url=ch.photo_url
            )
    return QueueStatusOut(
        queue_id=qrow.id,
        status=qrow.status,  # type: ignore[arg-type]
        error_reason=qrow.error_reason,
        channel=channel,
    )


@router.delete("/{channel_id}", status_code=204)
async def remove_source(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await remove_user_source(db, user_id=user.id, channel_id=channel_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/{channel_id}/hide", status_code=204)
async def hide_source(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    if await db.get(Channel, channel_id) is None:
        raise APIError(code="channel_not_found", message="Channel not found", status_code=404)
    await hide_channel_repo(db, user_id=user.id, channel_id=channel_id)
    await db.commit()
    return Response(status_code=204)
