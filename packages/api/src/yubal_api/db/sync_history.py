"""Sync history database model."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SyncHistory(SQLModel, table=True):
    """A completed sync job record."""

    __tablename__ = "sync_history"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source: str = Field(max_length=50)  # "manual" / "scheduler"
    status: str = Field(max_length=50)  # "completed" / "failed" / "cancelled"
    track_count: int | None = Field(default=None)
    tracks_added: int = Field(default=0)
    tracks_failed: int = Field(default=0)
    tracks_skipped: int = Field(default=0)
    orphans_deleted: int = Field(default=0)
    orphans_kept: int = Field(default=0)
    audio_codec: str | None = Field(default=None, max_length=20)
    audio_bitrate: int | None = Field(default=None)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
