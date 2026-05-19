"""channels: hidden flag (global hide-from-catalog)

Revision ID: 0009_channels_hidden
Revises: 0008_user_catalog_hidden
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_channels_hidden"
down_revision: Union[str, Sequence[str], None] = "0008_user_catalog_hidden"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "hidden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("channels", "hidden")
