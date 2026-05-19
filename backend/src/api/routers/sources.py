from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.channel_photo import channel_photo_url
from api.deps import get_current_user, get_db
from api.errors import APIError
from api.parse_source_input import ParseError, parse_source_input
from api.rate_limit import sources_user_rate_limit
from api.schemas.sources import (
    AddSourceIn,
    AddSourceOut,
    ChannelSummary,
    HiddenSourceItem,
    HiddenSourceList,
    QueueStatusOut,
    SourceList,
    SourceListItem,
)
from shared.models import Channel, ChannelJoinQueue, ChannelSubscription, User
from shared.repositories.user_sources import (
    add_user_source,
    list_user_sources,
    remove_user_source,
)
from shared.repositories.user_states import (
    hide_channel as hide_channel_repo,
    list_hidden_channels,
    unhide_channel as unhide_channel_repo,
)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post(
    "",
    response_model=None,
    responses={
        200: {"model": AddSourceOut},
        202: {"model": AddSourceOut},
    },
    dependencies=[Depends(sources_user_rate_limit)],
)
async def add_source(
    body: AddSourceIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AddSourceOut | JSONResponse:
    try:
        parsed = parse_source_input(body.input)
    except ParseError as exc:
        raise APIError(
            code="invalid_source_input",
            message="Invalid source input",
            status_code=400,
        ) from exc

    if parsed.kind == "public_username":
        assert parsed.username is not None  # narrowed by parser
        return await _add_public_source(db, user, username=parsed.username)
    assert parsed.invite_hash is not None  # narrowed by parser
    return await _add_private_source(db, user, invite_hash=parsed.invite_hash)


async def _add_public_source(
    db: AsyncSession, user: User, *, username: str
) -> AddSourceOut | JSONResponse:
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
                id=ch.id, username=ch.username, title=ch.title,
                photo_url=channel_photo_url(ch.id, ch.photo_storage_key),
            ),
        )

    queue_row = ChannelJoinQueue(
        kind="public_username",
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


async def _add_private_source(
    db: AsyncSession, user: User, *, invite_hash: str
) -> JSONResponse:
    queue_row = ChannelJoinQueue(
        kind="private_invite",
        invite_hash=invite_hash,
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
                    photo_url=channel_photo_url(row.channel_id, row.channel_photo_storage_key),
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
                id=ch.id, username=ch.username, title=ch.title,
                photo_url=channel_photo_url(ch.id, ch.photo_storage_key),
            )
    return QueueStatusOut(
        queue_id=qrow.id,
        status=qrow.status,  # type: ignore[arg-type]
        error_code=qrow.error_code,
        error_reason=qrow.error_reason,
        channel=channel,
    )


@router.get("/hidden", response_model=HiddenSourceList)
async def get_hidden_sources(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HiddenSourceList:
    rows = await list_hidden_channels(db, user_id=user.id)
    return HiddenSourceList(
        items=[
            HiddenSourceItem(
                channel=ChannelSummary(
                    id=row.channel_id,
                    username=row.channel_username,
                    title=row.channel_title,
                    photo_url=channel_photo_url(row.channel_id, row.channel_photo_storage_key),
                ),
                hidden_at=row.hidden_at,
            )
            for row in rows
        ]
    )


@router.post("/{channel_id}", response_model=AddSourceOut)
async def subscribe_by_channel_id(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AddSourceOut:
    ch = await db.get(Channel, channel_id)
    if ch is None:
        raise APIError(
            code="channel_not_found", message="Channel not found", status_code=404
        )
    if ch.banned:
        raise APIError(
            code="channel_banned", message="Channel is banned", status_code=403
        )
    sub = await db.get(ChannelSubscription, channel_id)
    if sub is None or sub.status != "active":
        raise APIError(
            code="channel_not_available",
            message="Channel is not available for subscription",
            status_code=404,
        )
    await add_user_source(db, user_id=user.id, channel_id=channel_id)
    await db.commit()
    return AddSourceOut(
        status="subscribed",
        channel=ChannelSummary(
            id=ch.id,
            username=ch.username,
            title=ch.title,
            photo_url=channel_photo_url(ch.id, ch.photo_storage_key),
        ),
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


@router.delete("/{channel_id}/hide", status_code=204)
async def unhide_source(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await unhide_channel_repo(db, user_id=user.id, channel_id=channel_id)
    await db.commit()
    return Response(status_code=204)
