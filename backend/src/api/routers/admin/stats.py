from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db
from shared.models import Admin, Channel, Post, User


router = APIRouter(prefix="/admin", tags=["admin"])


class StatsResponse(BaseModel):
    users_count: int
    channels_count: int
    banned_channels: int
    posts_count: int
    last_post_at: datetime | None


@router.get("/stats", response_model=StatsResponse)
async def stats(
    _: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    users_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    channels_count = (await db.execute(select(func.count(Channel.id)))).scalar_one()
    banned_channels = (await db.execute(
        select(func.count(Channel.id)).where(Channel.banned.is_(True))
    )).scalar_one()
    posts_count = (await db.execute(select(func.count(Post.id)))).scalar_one()
    last_post_at = (await db.execute(select(func.max(Post.posted_at)))).scalar_one()
    return StatsResponse(
        users_count=users_count,
        channels_count=channels_count,
        banned_channels=banned_channels,
        posts_count=posts_count,
        last_post_at=last_post_at,
    )
