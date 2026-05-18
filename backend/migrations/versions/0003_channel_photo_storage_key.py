"""rename channels.photo_url to photo_storage_key

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-19 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("channels", "photo_url", new_column_name="photo_storage_key")


def downgrade() -> None:
    op.alter_column("channels", "photo_storage_key", new_column_name="photo_url")
