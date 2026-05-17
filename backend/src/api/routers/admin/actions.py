import base64
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db
from shared.models import Admin, AdminAction


router = APIRouter(prefix="/admin", tags=["admin"])


def _encode_cursor(last_id: int) -> str:
    return base64.urlsafe_b64encode(str(last_id).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    return int(base64.urlsafe_b64decode(cursor.encode()).decode())


class ActionOut(BaseModel):
    id: int
    admin_id: int | None
    admin_email: str | None
    action: str
    target: dict[str, Any] | None
    created_at: datetime


class ActionsListResponse(BaseModel):
    actions: list[ActionOut]
    next_cursor: str | None


@router.get("/admin-actions", response_model=ActionsListResponse)
async def list_admin_actions(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    admin_id: int | None = Query(default=None),
    _: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ActionsListResponse:
    stmt = (
        select(
            AdminAction.id,
            AdminAction.admin_id,
            Admin.email.label("admin_email"),
            AdminAction.action,
            AdminAction.target,
            AdminAction.created_at,
        )
        .select_from(AdminAction)
        .outerjoin(Admin, Admin.id == AdminAction.admin_id)
        .order_by(AdminAction.id.desc())
        .limit(limit + 1)
    )
    if action:
        stmt = stmt.where(AdminAction.action == action)
    if admin_id is not None:
        stmt = stmt.where(AdminAction.admin_id == admin_id)
    if cursor:
        last_id = _decode_cursor(cursor)
        stmt = stmt.where(AdminAction.id < last_id)

    res = await db.execute(stmt)
    rows = list(res.mappings().all())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _encode_cursor(rows[-1]["id"])

    return ActionsListResponse(
        actions=[ActionOut(**dict(r)) for r in rows],
        next_cursor=next_cursor,
    )
