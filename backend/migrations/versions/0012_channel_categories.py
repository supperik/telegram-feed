"""channel_categories: M2M link of channels to fixed category slugs

Revision ID: 0012_channel_categories
Revises: 0011_channel_backfill_state
Create Date: 2026-05-25

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_channel_categories"
down_revision: Union[str, Sequence[str], None] = "0011_channel_backfill_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_categories",
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id", "category"),
    )
    op.create_index(
        "ix_channel_categories_category",
        "channel_categories",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index("ix_channel_categories_category", table_name="channel_categories")
    op.drop_table("channel_categories")
