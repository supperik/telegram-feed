"""posts.tg_grouped_id + partial index for album lookup

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-19 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("tg_grouped_id", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "uq_posts_channel_id_tg_grouped_id",
        "posts",
        ["channel_id", "tg_grouped_id"],
        unique=True,
        postgresql_where=sa.text("tg_grouped_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_posts_channel_id_tg_grouped_id",
        table_name="posts",
        postgresql_where=sa.text("tg_grouped_id IS NOT NULL"),
    )
    op.drop_column("posts", "tg_grouped_id")
