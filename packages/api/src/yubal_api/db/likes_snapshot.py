"""Likes snapshot database model."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class LikesSnapshot(SQLModel, table=True):
    """Last-seen state of a liked song, used to detect YT-side changes.

    ``title``/``artists`` mirror what YouTube Music currently reports;
    ``synced_title``/``synced_artists`` capture the state at the last
    download. A divergence between the two means YT mutated the track's
    metadata since we last synced it.
    """

    __tablename__ = "likes_snapshot"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    video_id: str = Field(unique=True, index=True)
    title: str
    artists: str  # JSON-encoded list of artist names
    duration_seconds: int | None = Field(default=None)
    synced_title: str | None = Field(default=None)
    synced_artists: str | None = Field(default=None)
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
