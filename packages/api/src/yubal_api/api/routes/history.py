"""History API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from yubal_api.api.deps import HistoryRepositoryDep
from yubal_api.schemas.history import (
    SyncDetailResponse,
    SyncHistoryResponse,
    SyncListResponse,
    TrackEventListResponse,
    TrackEventResponse,
)

router = APIRouter(tags=["history"])


@router.get("/history")
async def list_syncs(
    history: HistoryRepositoryDep,
    limit: int = 20,
    offset: int = 0,
) -> SyncListResponse:
    """List sync history (newest first, paginated)."""
    syncs = history.list_syncs(limit=limit, offset=offset)
    total = history.count_syncs()
    return SyncListResponse(
        items=[SyncHistoryResponse.model_validate(s, from_attributes=True) for s in syncs],
        total=total,
    )


@router.get("/history/{sync_id}")
async def get_sync_detail(
    sync_id: UUID,
    history: HistoryRepositoryDep,
) -> SyncDetailResponse:
    """Get a single sync with its track events."""
    sync = history.get_sync(sync_id)
    if sync is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync not found")

    events = history.list_track_events(sync_id=sync_id, limit=1000)
    return SyncDetailResponse(
        sync=SyncHistoryResponse.model_validate(sync, from_attributes=True),
        track_events=[TrackEventResponse.model_validate(e, from_attributes=True) for e in events],
    )


@router.get("/tracks")
async def list_track_events(
    history: HistoryRepositoryDep,
    event: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> TrackEventListResponse:
    """List track events (filterable by event type, paginated)."""
    events = history.list_track_events(event=event, limit=limit, offset=offset)
    total = history.count_track_events(event=event)
    return TrackEventListResponse(
        items=[TrackEventResponse.model_validate(e, from_attributes=True) for e in events],
        total=total,
    )
