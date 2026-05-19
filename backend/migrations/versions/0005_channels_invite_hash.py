"""channels: invite_hash + backfill from queue

Revision ID: 0005_channels_invite_hash
Revises: 0004_private_invite_queue
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_channels_invite_hash"
down_revision: Union[str, Sequence[str], None] = "0004_private_invite_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("invite_hash", sa.String(length=128), nullable=True),
    )
    op.execute(
        """
        UPDATE channels c SET invite_hash = sub.invite_hash
        FROM (
          SELECT DISTINCT ON (channel_id) channel_id, invite_hash
          FROM channel_join_queue
          WHERE kind = 'private_invite'
            AND status = 'done'
            AND invite_hash IS NOT NULL
            AND channel_id IS NOT NULL
          ORDER BY channel_id, updated_at DESC NULLS LAST, id DESC
        ) sub
        WHERE c.id = sub.channel_id
          AND c.invite_hash IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_column("channels", "invite_hash")
