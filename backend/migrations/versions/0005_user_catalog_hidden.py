"""user_catalog_hidden_channels: per-user hidden-from-catalog list

Revision ID: 0005_user_catalog_hidden
Revises: 0004_private_invite_queue
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_user_catalog_hidden"
down_revision: Union[str, Sequence[str], None] = "0004_private_invite_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_catalog_hidden_channels",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "hidden_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.PrimaryKeyConstraint("user_id", "channel_id"),
    )


def downgrade() -> None:
    op.drop_table("user_catalog_hidden_channels")
