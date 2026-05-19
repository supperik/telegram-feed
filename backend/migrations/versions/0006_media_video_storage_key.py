"""media: video_storage_key

Revision ID: 0006_media_video_storage_key
Revises: 0005_channels_invite_hash
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_media_video_storage_key"
down_revision: Union[str, Sequence[str], None] = "0005_channels_invite_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column("video_storage_key", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("media", "video_storage_key")
