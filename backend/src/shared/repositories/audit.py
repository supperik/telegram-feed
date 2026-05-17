from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import AdminAction


async def append_admin_action(
    session: AsyncSession,
    *,
    admin_id: int,
    action: str,
    target: dict[str, Any],
) -> None:
    """Append an immutable row to admin_actions. Caller commits."""
    await session.execute(
        insert(AdminAction).values(
            admin_id=admin_id,
            action=action,
            target=target,
        )
    )
