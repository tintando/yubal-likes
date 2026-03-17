"""Database repository for keep list."""

from sqlalchemy import Engine
from sqlmodel import Session, select

from yubal_api.db.keep_list import KeepListEntry


class KeepListRepository:
    """Repository for keep list database operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, path: str) -> None:
        """Add a path to the keep list (no-op if already present)."""
        with Session(self._engine) as session:
            stmt = select(KeepListEntry).where(KeepListEntry.path == path)
            if session.exec(stmt).first() is not None:
                return
            session.add(KeepListEntry(path=path))
            session.commit()

    def remove(self, path: str) -> bool:
        """Remove a path from the keep list. Returns True if removed."""
        with Session(self._engine) as session:
            stmt = select(KeepListEntry).where(KeepListEntry.path == path)
            entry = session.exec(stmt).first()
            if entry is None:
                return False
            session.delete(entry)
            session.commit()
            return True

    def contains(self, path: str) -> bool:
        """Check if a path is in the keep list."""
        with Session(self._engine) as session:
            stmt = select(KeepListEntry).where(KeepListEntry.path == path)
            return session.exec(stmt).first() is not None

    def list_all(self) -> list[str]:
        """List all paths in the keep list."""
        with Session(self._engine) as session:
            stmt = select(KeepListEntry).order_by(KeepListEntry.path)
            return [entry.path for entry in session.exec(stmt).all()]
