from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from api.errors import APIError
from shared.models import Post, User
from shared.repositories.user_states import (
    hide_post as hide_post_repo,
    save_post,
    unsave_post,
)


router = APIRouter(prefix="/posts", tags=["posts"])


async def _require_post(db: AsyncSession, post_id: int) -> None:
    if await db.get(Post, post_id) is None:
        raise APIError(code="post_not_found", message="Post not found", status_code=404)


@router.post("/{post_id}/save", status_code=204)
async def save(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await _require_post(db, post_id)
    await save_post(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)


@router.delete("/{post_id}/save", status_code=204)
async def unsave(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await unsave_post(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/{post_id}/hide", status_code=204)
async def hide(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    await _require_post(db, post_id)
    await hide_post_repo(db, user_id=user.id, post_id=post_id)
    await db.commit()
    return Response(status_code=204)
