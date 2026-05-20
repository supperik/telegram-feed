"""channel_backfill_state: per-channel lazy-history-backfill cursor + lock

Revision ID: 0011_channel_backfill_state
Revises: 0010_user_read_posts
Create Date: 2026-05-20

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_channel_backfill_state"
down_revision: Union[str, Sequence[str], None] = "0010_user_read_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_backfill_state",
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "fully_backfilled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("oldest_seen_msg_id", sa.Integer(), nullable=True),
        sa.Column("last_backfill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id"),
    )
    op.create_index(
        "ix_channel_backfill_state_active",
        "channel_backfill_state",
        ["channel_id"],
        unique=False,
        postgresql_where=sa.text("NOT fully_backfilled"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_channel_backfill_state_active", table_name="channel_backfill_state"
    )
    op.drop_table("channel_backfill_state")
