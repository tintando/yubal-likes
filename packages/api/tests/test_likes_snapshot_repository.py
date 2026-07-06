"""Tests for LikesSnapshotRepository state machine."""

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from yubal_api.db.likes_snapshot import LikesSnapshot
from yubal_api.db.likes_snapshot_repository import (
    LikesSnapshotRepository,
    LiveTrack,
)


@pytest.fixture
def repo(engine: Engine) -> LikesSnapshotRepository:
    return LikesSnapshotRepository(engine)


def track(
    video_id: str = "vid00000001",
    title: str = "Song Title",
    artists: list[str] | None = None,
    duration: int | None = 180,
) -> LiveTrack:
    return LiveTrack(
        video_id=video_id,
        title=title,
        artists=artists if artists is not None else ["Artist"],
        duration_seconds=duration,
    )


def get_row(engine: Engine, video_id: str) -> LikesSnapshot | None:
    with Session(engine) as session:
        stmt = select(LikesSnapshot).where(LikesSnapshot.video_id == video_id)
        return session.exec(stmt).first()


class TestSyncPlaylist:
    def test_first_sight_is_new_with_baseline(
        self, repo: LikesSnapshotRepository, engine: Engine
    ) -> None:
        result = repo.sync_playlist([track()])

        assert result["vid00000001"] == ("new", None)
        row = get_row(engine, "vid00000001")
        assert row is not None
        assert row.synced_title == "Song Title"
        assert row.synced_artists == row.artists

    def test_unchanged_relist_is_synced_and_bumps_last_seen(
        self, repo: LikesSnapshotRepository, engine: Engine
    ) -> None:
        repo.sync_playlist([track()])
        first = get_row(engine, "vid00000001")
        assert first is not None

        result = repo.sync_playlist([track()])

        assert result["vid00000001"] == ("synced", None)
        row = get_row(engine, "vid00000001")
        assert row is not None
        assert row.last_seen >= first.last_seen

    def test_title_change_is_changed_with_synced_title_preserved(
        self, repo: LikesSnapshotRepository, engine: Engine
    ) -> None:
        repo.sync_playlist([track(title="Old Title")])

        result = repo.sync_playlist([track(title="New Title")])

        assert result["vid00000001"] == ("changed", "Old Title")
        row = get_row(engine, "vid00000001")
        assert row is not None
        assert row.title == "New Title"
        assert row.synced_title == "Old Title"

    def test_artists_only_change_is_changed(
        self, repo: LikesSnapshotRepository
    ) -> None:
        repo.sync_playlist([track(artists=["Artist"])])

        result = repo.sync_playlist([track(artists=["Artist", "Guest"])])

        status, _ = result["vid00000001"]
        assert status == "changed"

    def test_changed_stays_changed_until_marked(
        self, repo: LikesSnapshotRepository
    ) -> None:
        repo.sync_playlist([track(title="Old Title")])
        repo.sync_playlist([track(title="New Title")])

        result = repo.sync_playlist([track(title="New Title")])

        assert result["vid00000001"] == ("changed", "Old Title")

    def test_prune_and_relike_restarts_as_new(
        self, repo: LikesSnapshotRepository, engine: Engine
    ) -> None:
        repo.sync_playlist([track()])

        # Unliked: id absent from playlist -> row pruned
        repo.sync_playlist([track(video_id="vid00000002")])
        assert get_row(engine, "vid00000001") is None

        # Re-liked: starts over as new
        result = repo.sync_playlist([track(), track(video_id="vid00000002")])
        assert result["vid00000001"] == ("new", None)
        assert result["vid00000002"] == ("synced", None)


class TestMarkSynced:
    def test_mark_synced_clears_changed(self, repo: LikesSnapshotRepository) -> None:
        repo.sync_playlist([track(title="Old Title")])
        repo.sync_playlist([track(title="New Title")])

        assert repo.mark_synced("vid00000001") is True

        result = repo.sync_playlist([track(title="New Title")])
        assert result["vid00000001"] == ("synced", None)

    def test_mark_synced_missing_id_returns_false(
        self, repo: LikesSnapshotRepository
    ) -> None:
        assert repo.mark_synced("missing00id") is False
