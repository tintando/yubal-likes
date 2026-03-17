"""Track event database model."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class TrackEvent(SQLModel, table=True):
    """An individual track addition or deletion event."""

    __tablename__ = "track_events"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sync_id: UUID | None = Field(default=None, foreign_key="sync_history.id", index=True)
    event: str = Field(max_length=20)  # "added" / "deleted"
    path: str  # Relative file path
    title: str | None = Field(default=None)
    artist: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
