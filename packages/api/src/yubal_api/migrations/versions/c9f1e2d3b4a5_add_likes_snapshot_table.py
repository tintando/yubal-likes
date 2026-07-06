"""Add likes snapshot table

Revision ID: c9f1e2d3b4a5
Revises: a1b2c3d4e5f6
Create Date: 2026-07-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f1e2d3b4a5"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "likes_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.VARCHAR(), nullable=False),
        sa.Column("title", sa.VARCHAR(), nullable=False),
        sa.Column("artists", sa.VARCHAR(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("synced_title", sa.VARCHAR(), nullable=True),
        sa.Column("synced_artists", sa.VARCHAR(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_likes_snapshot_video_id", "likes_snapshot", ["video_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_likes_snapshot_video_id", table_name="likes_snapshot")
    op.drop_table("likes_snapshot")
