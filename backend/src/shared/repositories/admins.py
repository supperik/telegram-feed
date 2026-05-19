import base64
import json
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Channel, ChannelSubscription, Post


MAX_CHANNELS_LIMIT = 200

SortField = Literal[
    "id", "username", "posts_count", "ref_count", "last_post_at", "banned", "hidden"
]
SortOrder = Literal["asc", "desc"]

SORTABLE_FIELDS: tuple[str, ...] = (
    "id", "username", "posts_count", "ref_count", "last_post_at", "banned", "hidden",
)
DEFAULT_SORT: SortField = "last_post_at"
DEFAULT_ORDER: SortOrder = "desc"
# Fields that are nullable in the result; sort uses NULLS LAST for these.
_NULLABLE_SORT_FIELDS = frozenset({"username", "last_post_at"})


def _admin_channel_select():
    """SELECT used by both list and single-channel admin views.

    Returns (stmt, sortable_cols) where sortable_cols maps a public sort name
    to its SQL expression. posts_count and last_post_at are derived from the
    posts table (the matching columns on `channels` are not maintained).
    """
    posts_agg = (
        select(
            Post.channel_id.label("channel_id"),
            func.count(Post.id).label("posts_count"),
            func.max(Post.posted_at).label("last_post_at"),
        )
        .group_by(Post.channel_id)
        .subquery()
    )
    last_post_col = posts_agg.c.last_post_at
    posts_count_col = func.coalesce(posts_agg.c.posts_count, 0)
    ref_count_col = func.coalesce(ChannelSubscription.ref_count, 0)

    stmt = (
        select(
            Channel.id,
            Channel.tg_chat_id,
            Channel.username,
            Channel.title,
            Channel.description,
            Channel.photo_storage_key,
            posts_count_col.label("posts_count"),
            Channel.banned,
            Channel.banned_reason,
            Channel.hidden,
            last_post_col.label("last_post_at"),
            Channel.created_at,
            ref_count_col.label("ref_count"),
        )
        .select_from(Channel)
        .outerjoin(posts_agg, posts_agg.c.channel_id == Channel.id)
        .outerjoin(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
    )
    sortable_cols: dict[str, Any] = {
        "id": Channel.id,
        "username": Channel.username,
        "posts_count": posts_count_col,
        "ref_count": ref_count_col,
        "last_post_at": last_post_col,
        "banned": Channel.banned,
        "hidden": Channel.hidden,
    }
    return stmt, sortable_cols


def _encode_sort_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def _decode_sort_value(raw: Any, sort: str) -> Any:
    if raw is None:
        return None
    if sort == "last_post_at":
        return datetime.fromisoformat(raw)
    if sort in ("banned", "hidden"):
        return bool(raw)
    return raw


def _encode_cursor(
    banned: bool, sort_value: Any, channel_id: int, sort: str, order: str
) -> str:
    payload = {
        "b": int(banned),
        "v": _encode_sort_value(sort_value),
        "id": channel_id,
        "s": sort,
        "o": order,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[bool, Any, int, str, str]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    sort = payload["s"]
    order = payload["o"]
    return (
        bool(payload["b"]),
        _decode_sort_value(payload["v"], sort),
        int(payload["id"]),
        sort,
        order,
    )


def _value_after_cursor(col, c_val: Any, order: str, nullable: bool):
    """`col` row that comes strictly after the cursor under the given order
    with NULLS LAST."""
    if c_val is None:
        # Cursor row was on the NULL tail (only possible if nullable).
        # Nothing in this col bucket comes after a NULL under NULLS LAST.
        return None
    if order == "desc":
        cond = col < c_val
    else:
        cond = col > c_val
    if nullable:
        cond = or_(cond, col.is_(None))
    return cond


async def list_channels_for_admin(
    session: AsyncSession,
    *,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    sort: str = DEFAULT_SORT,
    order: str = DEFAULT_ORDER,
) -> tuple[list[dict[str, Any]], str | None]:
    """Paginated channel list with metrics.

    Sort key is one of SORTABLE_FIELDS; banned-first is preserved as the
    primary compound key whenever the user-selected sort is not `banned`.
    Tie-break is always `id DESC`. posts_count and last_post_at are computed
    live from the posts table (the matching channels columns are dead).
    """
    if sort not in SORTABLE_FIELDS:
        raise ValueError(f"unknown sort field: {sort}")
    if order not in ("asc", "desc"):
        raise ValueError(f"unknown order: {order}")

    limit = max(1, min(MAX_CHANNELS_LIMIT, limit))
    stmt, sortable = _admin_channel_select()
    sort_col = sortable[sort]
    nullable = sort in _NULLABLE_SORT_FIELDS

    primary_sorted_by_banned = sort != "banned"
    sort_expr = sort_col.desc() if order == "desc" else sort_col.asc()
    if nullable:
        sort_expr = sort_expr.nulls_last()

    order_by: list[Any] = []
    if primary_sorted_by_banned:
        order_by.append(Channel.banned.desc())
    order_by.append(sort_expr)
    order_by.append(Channel.id.desc())
    stmt = stmt.order_by(*order_by).limit(limit + 1)

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Channel.username.ilike(pattern),
                Channel.title.ilike(pattern),
            )
        )

    if cursor:
        c_banned, c_val, c_id, c_sort, c_order = _decode_cursor(cursor)
        if c_sort != sort or c_order != order:
            raise ValueError("cursor sort/order mismatch")

        # "row after cursor" under (banned DESC?, sort_col <order> [NULLS LAST], id DESC).
        sort_after = _value_after_cursor(sort_col, c_val, order, nullable)
        same_sort = sort_col.is_(c_val) if c_val is None else sort_col == c_val
        same_row_smaller_id = and_(same_sort, Channel.id < c_id)

        if primary_sorted_by_banned:
            in_lower_banned = Channel.banned < c_banned
            in_same_banned_after_sort = and_(Channel.banned == c_banned, sort_after) \
                if sort_after is not None else None
            in_same_banned_same_sort = and_(Channel.banned == c_banned, same_row_smaller_id)
            clauses = [in_lower_banned, in_same_banned_same_sort]
            if in_same_banned_after_sort is not None:
                clauses.insert(1, in_same_banned_after_sort)
            stmt = stmt.where(or_(*clauses))
        else:
            # sort == banned. Encode value is the banned itself.
            clauses = [same_row_smaller_id]
            if sort_after is not None:
                clauses.append(sort_after)
            stmt = stmt.where(or_(*clauses))

    res = await session.execute(stmt)
    rows = list(res.mappings().all())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(
            last["banned"], last[sort], last["id"], sort, order,
        )

    return [dict(r) for r in rows], next_cursor


async def get_channel_row_for_admin(
    session: AsyncSession, channel_id: int
) -> dict[str, Any] | None:
    """Single-channel variant of list_channels_for_admin: same shape (incl.
    aggregated posts_count / last_post_at / ref_count), filtered by id."""
    stmt, _ = _admin_channel_select()
    stmt = stmt.where(Channel.id == channel_id)
    res = await session.execute(stmt)
    row = res.mappings().first()
    return dict(row) if row else None


async def get_channel_or_none(session: AsyncSession, channel_id: int) -> Channel | None:
    res = await session.execute(select(Channel).where(Channel.id == channel_id))
    return res.scalar_one_or_none()


async def ban_channel(session: AsyncSession, channel_id: int, reason: str) -> Channel | None:
    res = await session.execute(
        update(Channel)
        .where(Channel.id == channel_id)
        .values(banned=True, banned_reason=reason)
        .returning(Channel)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()


async def unban_channel(session: AsyncSession, channel_id: int) -> Channel | None:
    res = await session.execute(
        update(Channel)
        .where(Channel.id == channel_id)
        .values(banned=False, banned_reason=None)
        .returning(Channel)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()


async def hide_channel(session: AsyncSession, channel_id: int) -> Channel | None:
    res = await session.execute(
        update(Channel)
        .where(Channel.id == channel_id)
        .values(hidden=True)
        .returning(Channel)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()


async def unhide_channel(session: AsyncSession, channel_id: int) -> Channel | None:
    res = await session.execute(
        update(Channel)
        .where(Channel.id == channel_id)
        .values(hidden=False)
        .returning(Channel)
        .execution_options(populate_existing=True)
    )
    return res.scalar_one_or_none()
