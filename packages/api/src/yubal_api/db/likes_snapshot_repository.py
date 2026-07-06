"""Database repository for likes snapshots."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Session, select

from yubal_api.db.likes_snapshot import LikesSnapshot

LikesStatus = str  # "new" | "changed" | "synced"


@dataclass(frozen=True)
class LiveTrack:
    """Current state of a liked song as reported by YouTube Music."""

    video_id: str
    title: str
    artists: list[str]
    duration_seconds: int | None = None


def _dump_artists(artists: list[str]) -> str:
    return json.dumps(artists, ensure_ascii=False)


def _artists_equal(stored_json: str | None, live: list[str]) -> bool:
    if stored_json is None:
        return False
    try:
        return json.loads(stored_json) == live
    except (json.JSONDecodeError, TypeError):
        return False


class LikesSnapshotRepository:
    """Repository for likes snapshot database operations."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def sync_playlist(
        self, tracks: list[LiveTrack]
    ) -> dict[str, tuple[LikesStatus, str | None]]:
        """Reconcile the snapshot table with the live liked-songs playlist.

        Upserts a row per live track, prunes rows whose video_id left the
        playlist, and returns per-track status:

        - ``new``: first sighting; synced_* baselined to the live values.
        - ``synced``: live state matches the last-synced state.
        - ``changed``: YT mutated title/artists since the last sync;
          synced_* is left untouched so the divergence stays visible.
        """
        now = datetime.now(UTC)
        result: dict[str, tuple[LikesStatus, str | None]] = {}
        live_ids = {t.video_id for t in tracks}

        with Session(self._engine) as session:
            rows = session.exec(select(LikesSnapshot)).all()
            by_id = {row.video_id: row for row in rows}

            # Prune rows for songs that were unliked; a re-like starts
            # over as "new" (correct - a fresh download follows).
            for row in rows:
                if row.video_id not in live_ids:
                    session.delete(row)

            for track in tracks:
                row = by_id.get(track.video_id)
                artists_json = _dump_artists(track.artists)

                if row is None:
                    session.add(
                        LikesSnapshot(
                            video_id=track.video_id,
                            title=track.title,
                            artists=artists_json,
                            duration_seconds=track.duration_seconds,
                            synced_title=track.title,
                            synced_artists=artists_json,
                            first_seen=now,
                            last_seen=now,
                        )
                    )
                    result[track.video_id] = ("new", None)
                    continue

                title_matches = (row.synced_title or "").strip() == track.title.strip()
                unchanged = title_matches and _artists_equal(
                    row.synced_artists, track.artists
                )

                row.title = track.title
                row.artists = artists_json
                row.duration_seconds = track.duration_seconds
                row.last_seen = now
                session.add(row)

                if unchanged:
                    result[track.video_id] = ("synced", None)
                else:
                    result[track.video_id] = ("changed", row.synced_title)

            session.commit()

        return result

    def mark_synced(self, video_id: str) -> bool:
        """Baseline synced_* to the live state. Returns False if unknown id."""
        with Session(self._engine) as session:
            stmt = select(LikesSnapshot).where(LikesSnapshot.video_id == video_id)
            row = session.exec(stmt).first()
            if row is None:
                return False
            row.synced_title = row.title
            row.synced_artists = row.artists
            session.add(row)
            session.commit()
            return True
