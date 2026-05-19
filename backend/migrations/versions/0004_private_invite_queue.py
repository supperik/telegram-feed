"""private invite queue: kind, invite_hash, error_code

Revision ID: 0004_private_invite_queue
Revises: 0003
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_private_invite_queue"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "channel_join_queue",
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            server_default="public_username",
        ),
    )
    op.add_column(
        "channel_join_queue",
        sa.Column("invite_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "channel_join_queue",
        sa.Column("error_code", sa.String(length=64), nullable=True),
    )
    op.alter_column(
        "channel_join_queue",
        "channel_username",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.create_check_constraint(
        op.f("ck_channel_join_queue_kind_chk"),
        "channel_join_queue",
        "(kind = 'public_username' AND channel_username IS NOT NULL AND invite_hash IS NULL) "
        "OR (kind = 'private_invite' AND invite_hash IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_channel_join_queue_kind_chk"),
        "channel_join_queue",
        type_="check",
    )
    op.alter_column(
        "channel_join_queue",
        "channel_username",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_column("channel_join_queue", "error_code")
    op.drop_column("channel_join_queue", "invite_hash")
    op.drop_column("channel_join_queue", "kind")
