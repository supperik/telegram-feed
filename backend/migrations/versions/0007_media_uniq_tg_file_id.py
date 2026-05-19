"""media: dedupe (post_id, tg_file_id) and add UNIQUE index

Cleans up rows accidentally inserted by upsert_post's album-append branch
on repeated catchup_channels runs (each ingester restart re-fed the album
tail), then enforces uniqueness at the schema level so it can't recur.

Revision ID: 0007_media_unique_post_id_tg_file_id
Revises: 0006_media_video_storage_key
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_media_unique_post_id_tg_file_id"
down_revision: Union[str, Sequence[str], None] = "0006_media_video_storage_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM media
            WHERE tg_file_id IS NOT NULL
              AND id NOT IN (
                  SELECT MIN(id) FROM media
                  WHERE tg_file_id IS NOT NULL
                  GROUP BY post_id, tg_file_id
              )
            """
        )
    )
    op.create_index(
        "uq_media_post_id_tg_file_id",
        "media",
        ["post_id", "tg_file_id"],
        unique=True,
        postgresql_where=sa.text("tg_file_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_media_post_id_tg_file_id",
        table_name="media",
        postgresql_where=sa.text("tg_file_id IS NOT NULL"),
    )
