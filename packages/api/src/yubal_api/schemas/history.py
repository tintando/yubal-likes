"""History API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SyncHistoryResponse(BaseModel):
    """A sync history record."""

    id: UUID
    source: str
    status: str
    track_count: int | None
    tracks_added: int
    tracks_failed: int
    tracks_skipped: int
    orphans_deleted: int
    orphans_kept: int
    audio_codec: str | None
    audio_bitrate: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TrackEventResponse(BaseModel):
    """A track event record."""

    id: UUID
    sync_id: UUID | None
    event: str
    path: str
    title: str | None
    artist: str | None
    created_at: datetime


class SyncListResponse(BaseModel):
    """Paginated list of sync history."""

    items: list[SyncHistoryResponse]
    total: int


class SyncDetailResponse(BaseModel):
    """Single sync with its track events."""

    sync: SyncHistoryResponse
    track_events: list[TrackEventResponse]


class TrackEventListResponse(BaseModel):
    """Paginated list of track events."""

    items: list[TrackEventResponse]
    total: int
