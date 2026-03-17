"""Persistent extraction cache backed by SQLite."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from types import TracebackType

from yubal.models.enums import MatchResult
from yubal.models.track import TrackMetadata

logger = logging.getLogger(__name__)

CACHE_DB = "extraction_cache.db"


class ExtractionCache:
    """Persistent cache of previously extracted track metadata.

    Stores TrackMetadata by source_video_id in a SQLite database.
    Used to skip expensive YouTube Music API calls for already-processed tracks.

    Only confidently matched tracks are cached (MatchResult.MATCHED).
    Unmatched, unofficial, and error-fallback tracks are excluded so they
    can be re-attempted on subsequent syncs.

    Usage::

        cache = ExtractionCache(cache_dir)
        with cache:
            track = cache.get("video_id")
            cache.add(metadata)
    """

    def __init__(
        self, cache_dir: Path, *, unmatched_expiry_days: int = 30
    ) -> None:
        self._path = cache_dir / CACHE_DB
        self._conn: sqlite3.Connection | None = None
        self._unmatched_expiry_seconds = unmatched_expiry_days * 86400

    def load(self) -> None:
        """Open the database and ensure the schema exists."""
        if self._conn is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "  video_id TEXT PRIMARY KEY,"
            "  metadata TEXT NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS unmatched ("
            "  video_id TEXT PRIMARY KEY,"
            "  video_type TEXT NOT NULL,"
            "  cached_at INTEGER NOT NULL"
            ")"
        )
        self._conn.commit()

    def get(self, video_id: str) -> TrackMetadata | None:
        """Look up cached metadata by source video ID."""
        if self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT metadata FROM cache WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row is None:
            return None
        try:
            return TrackMetadata.model_validate_json(row[0])
        except Exception:
            return None

    def add(self, metadata: TrackMetadata) -> None:
        """Add a track to the cache if it's a confident match.

        Commits immediately so progress survives timeouts and crashes.
        Errors are logged and swallowed — losing a cache entry is better
        than crashing the sync.
        """
        if metadata.match_result != MatchResult.MATCHED:
            return
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (video_id, metadata) VALUES (?, ?)",
                (metadata.source_video_id, metadata.model_dump_json()),
            )
            self._conn.commit()
        except sqlite3.Error:
            logger.warning(
                "Failed to cache metadata for '%s'", metadata.title, exc_info=True
            )

    def is_unmatched(self, video_id: str) -> bool:
        """Check if a track is cached as unmatched.

        Returns False (and deletes the row) if the entry has expired.
        """
        if self._conn is None:
            return False
        row = self._conn.execute(
            "SELECT cached_at FROM unmatched WHERE video_id = ?", (video_id,)
        ).fetchone()
        if row is None:
            return False
        if time.time() - row[0] > self._unmatched_expiry_seconds:
            self._conn.execute(
                "DELETE FROM unmatched WHERE video_id = ?", (video_id,)
            )
            self._conn.commit()
            return False
        return True

    def add_unmatched(self, video_id: str, video_type: str) -> None:
        """Record a track as unmatched so future syncs skip the album search."""
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO unmatched (video_id, video_type, cached_at) "
                "VALUES (?, ?, ?)",
                (video_id, video_type, int(time.time())),
            )
            self._conn.commit()
        except sqlite3.Error:
            logger.warning(
                "Failed to cache unmatched status for '%s'", video_id, exc_info=True
            )

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> ExtractionCache:
        self.load()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def __len__(self) -> int:
        if self._conn is None:
            return 0
        row = self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()
        return row[0] if row else 0
