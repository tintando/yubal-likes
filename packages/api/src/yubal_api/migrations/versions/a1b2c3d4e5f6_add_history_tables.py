"""Add sync history, track events, and keep list tables

Revision ID: a1b2c3d4e5f6
Revises: 03132d5514f9
Create Date: 2026-03-17 00:00:00.000000

"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "03132d5514f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.VARCHAR(length=50), nullable=False),
        sa.Column("status", sa.VARCHAR(length=50), nullable=False),
        sa.Column("track_count", sa.Integer(), nullable=True),
        sa.Column("tracks_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tracks_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tracks_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphans_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("orphans_kept", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audio_codec", sa.VARCHAR(length=20), nullable=True),
        sa.Column("audio_bitrate", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "track_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sync_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.VARCHAR(length=20), nullable=False),
        sa.Column("path", sa.VARCHAR(), nullable=False),
        sa.Column("title", sa.VARCHAR(), nullable=True),
        sa.Column("artist", sa.VARCHAR(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sync_id"], ["sync_history.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_track_events_sync_id", "track_events", ["sync_id"])

    op.create_table(
        "keep_list",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.VARCHAR(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_keep_list_path", "keep_list", ["path"], unique=True)

    # Migrate data from .yubal_keep.json if it exists
    _migrate_keep_list_json()


def _migrate_keep_list_json() -> None:
    """Read .yubal_keep.json and insert entries into keep_list table."""
    # Try common data paths — the settings aren't available here,
    # so we check the env variable directly.
    import os

    root = os.environ.get("YUBAL_ROOT", "")
    if not root:
        return

    data_dir = os.environ.get("YUBAL_DATA", str(Path(root) / "data"))
    keep_file = Path(data_dir) / ".yubal_keep.json"

    if not keep_file.exists():
        return

    try:
        data = json.loads(keep_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return

        now = datetime.now(UTC)
        conn = op.get_bind()
        for path in data:
            if isinstance(path, str) and path.strip():
                conn.execute(
                    sa.text(
                        "INSERT INTO keep_list (id, path, created_at) VALUES (:id, :path, :created_at)"
                    ),
                    {"id": str(uuid.uuid4()), "path": path.strip(), "created_at": now},
                )

        keep_file.unlink()
    except (json.JSONDecodeError, OSError):
        pass  # Skip migration if file is corrupt


def downgrade() -> None:
    op.drop_table("keep_list")
    op.drop_index("ix_track_events_sync_id", table_name="track_events")
    op.drop_table("track_events")
    op.drop_table("sync_history")
