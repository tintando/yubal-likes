"""Database repository for sync history and track events."""

from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import Session, col, func, select

from yubal_api.db.sync_history import SyncHistory
from yubal_api.db.track_event import TrackEvent


class HistoryRepository:
    """Repository for sync history and track event operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record_sync(self, sync: SyncHistory) -> SyncHistory:
        """Insert a sync history row."""
        with Session(self._engine) as session:
            session.add(sync)
            session.commit()
            session.refresh(sync)
            return sync

    def update_sync(self, id: UUID, **fields: object) -> SyncHistory | None:
        """Update fields on a sync history row."""
        with Session(self._engine) as session:
            sync = session.get(SyncHistory, id)
            if sync is None:
                return None
            for key, value in fields.items():
                setattr(sync, key, value)
            session.commit()
            session.refresh(sync)
            return sync

    def record_track_events(self, events: list[TrackEvent]) -> None:
        """Bulk insert track events."""
        if not events:
            return
        with Session(self._engine) as session:
            for event in events:
                session.add(event)
            session.commit()

    def list_syncs(self, limit: int = 20, offset: int = 0) -> list[SyncHistory]:
        """List sync history, newest first."""
        with Session(self._engine) as session:
            stmt = (
                select(SyncHistory)
                .order_by(col(SyncHistory.created_at).desc())
                .offset(offset)
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    def count_syncs(self) -> int:
        """Count total sync history rows."""
        with Session(self._engine) as session:
            stmt = select(func.count()).select_from(SyncHistory)
            return session.exec(stmt).one()

    def get_sync(self, id: UUID) -> SyncHistory | None:
        """Get a single sync history row."""
        with Session(self._engine) as session:
            return session.get(SyncHistory, id)

    def list_track_events(
        self,
        *,
        sync_id: UUID | None = None,
        event: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TrackEvent]:
        """List track events with optional filters."""
        with Session(self._engine) as session:
            stmt = (
                select(TrackEvent)
                .order_by(col(TrackEvent.created_at).desc())
                .offset(offset)
                .limit(limit)
            )
            if sync_id is not None:
                stmt = stmt.where(TrackEvent.sync_id == sync_id)
            if event is not None:
                stmt = stmt.where(TrackEvent.event == event)
            return list(session.exec(stmt).all())

    def count_track_events(
        self,
        *,
        sync_id: UUID | None = None,
        event: str | None = None,
    ) -> int:
        """Count track events with optional filters."""
        with Session(self._engine) as session:
            stmt = select(func.count()).select_from(TrackEvent)
            if sync_id is not None:
                stmt = stmt.where(TrackEvent.sync_id == sync_id)
            if event is not None:
                stmt = stmt.where(TrackEvent.event == event)
            return session.exec(stmt).one()
