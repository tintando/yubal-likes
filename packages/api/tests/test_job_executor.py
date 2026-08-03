"""Tests for JobExecutor timeout enforcement."""

import time
from typing import Any
from uuid import UUID

import pytest
from yubal import AudioCodec, CancelToken
from yubal_api.domain.enums import JobSource, JobStatus
from yubal_api.domain.job import Job, OrphanFile
from yubal_api.services.job_executor import JobExecutor
from yubal_api.services.sync_service import SyncResult, SyncService


class FakeJobStore:
    """Minimal fake implementing the JobExecutionStore protocol."""

    def __init__(self) -> None:
        self.transitions: list[tuple[str, JobStatus]] = []
        self.transition_kwargs: list[dict[str, Any]] = []
        self.released: list[str] = []
        self._pending: list[Job] = []
        self.job: Job | None = None

    def get(self, job_id: str) -> Job | None:
        return self.job

    def create(
        self,
        url: str,
        audio_format: AudioCodec = AudioCodec.OPUS,
        max_items: int | None = None,
        source: JobSource = JobSource.MANUAL,
        subscription_id: UUID | None = None,
    ) -> tuple[Job, bool] | None:
        job = Job(id="test-job", url=url, audio_format=audio_format)
        return job, True

    def transition(self, job_id: str, status: JobStatus, **kwargs: Any) -> Job:
        self.transitions.append((job_id, status))
        self.transition_kwargs.append(kwargs)
        return Job(id=job_id, url="", audio_format=AudioCodec.OPUS, status=status)

    def pop_next_pending(self) -> Job | None:
        return self._pending.pop(0) if self._pending else None

    def release_active(self, job_id: str) -> bool:
        self.released.append(job_id)
        return True


@pytest.mark.enable_socket
class TestExecutorTimeout:
    """Tests for timeout enforcement in _run_job."""

    @pytest.fixture
    def store(self) -> FakeJobStore:
        return FakeJobStore()

    @pytest.fixture
    def executor(self, store: FakeJobStore, tmp_path: Any) -> JobExecutor:
        return JobExecutor(job_store=store, base_path=tmp_path, job_timeout=0.1)

    @pytest.mark.asyncio
    async def test_timeout_triggers_cancellation_and_fails_job(
        self,
        executor: JobExecutor,
        store: FakeJobStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Timeout should mark job FAILED and trigger cancel token."""

        def blocking_run(*_args: Any, **_kwargs: Any) -> SyncResult:
            time.sleep(0.5)
            return SyncResult(success=True)

        monkeypatch.setattr(
            "yubal_api.services.job_executor.SyncService.run",
            blocking_run,
        )

        await executor._run_job("test-job", "https://example.com")

        # Should have transitioned to FETCHING_INFO then FAILED
        statuses = [s for _, s in store.transitions]
        assert JobStatus.FETCHING_INFO in statuses
        assert statuses[-1] == JobStatus.FAILED

        # Cancel token cleaned up in finally
        assert "test-job" not in executor._cancel_tokens

        # Active slot should have been released
        assert "test-job" in store.released

    @pytest.mark.asyncio
    async def test_normal_completion_within_timeout(
        self,
        executor: JobExecutor,
        store: FakeJobStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Job finishing before timeout should complete normally."""

        def fast_run(*_args: Any, **_kwargs: Any) -> SyncResult:
            return SyncResult(success=True)

        monkeypatch.setattr(
            "yubal_api.services.job_executor.SyncService.run",
            fast_run,
        )

        await executor._run_job("test-job", "https://example.com")

        statuses = [s for _, s in store.transitions]
        assert JobStatus.COMPLETED in statuses
        assert JobStatus.FAILED not in statuses
        assert "test-job" in store.released


@pytest.mark.enable_socket
class TestExecutorAudioQuality:
    """Tests for audio_quality propagation through JobExecutor to SyncService."""

    @pytest.fixture
    def store(self) -> FakeJobStore:
        return FakeJobStore()

    @pytest.mark.asyncio
    async def test_audio_quality_passed_to_sync_service(
        self,
        store: FakeJobStore,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """audio_quality should be forwarded to SyncService."""
        executor = JobExecutor(job_store=store, base_path=tmp_path, audio_quality=5)

        captured_quality: list[int] = []

        original_init = SyncService.__init__

        def spy_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            captured_quality.append(self.audio_quality)

        monkeypatch.setattr(
            "yubal_api.services.job_executor.SyncService.__init__",
            spy_init,
        )
        monkeypatch.setattr(
            "yubal_api.services.job_executor.SyncService.run",
            lambda *a, **kw: SyncResult(success=True),
        )

        await executor._run_job("test-job", "https://example.com")

        assert captured_quality == [5]

    @pytest.mark.asyncio
    async def test_audio_quality_defaults_to_zero(
        self,
        store: FakeJobStore,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """audio_quality should default to 0 (best) when not specified."""
        executor = JobExecutor(job_store=store, base_path=tmp_path)

        captured_quality: list[int] = []

        original_init = SyncService.__init__

        def spy_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            captured_quality.append(self.audio_quality)

        monkeypatch.setattr(
            "yubal_api.services.job_executor.SyncService.__init__",
            spy_init,
        )
        monkeypatch.setattr(
            "yubal_api.services.job_executor.SyncService.run",
            lambda *a, **kw: SyncResult(success=True),
        )

        await executor._run_job("test-job", "https://example.com")

        assert captured_quality == [0]


@pytest.mark.enable_socket
class TestRunCleanupReplacements:
    """Tests for replacement annotation during orphan cleanup."""

    @pytest.fixture
    def store(self) -> FakeJobStore:
        return FakeJobStore()

    @pytest.fixture
    def executor(self, store: FakeJobStore, tmp_path: Any) -> JobExecutor:
        return JobExecutor(job_store=store, base_path=tmp_path)

    @pytest.mark.asyncio
    async def test_orphans_annotated_with_replacements(
        self,
        executor: JobExecutor,
        store: FakeJobStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Orphans matching an added track carry replaced_by into the store."""
        orphans = [
            OrphanFile(path="Artist/Album/01 - Song Title.opus", size=100),
            OrphanFile(path="Other/Album/05 - Unrelated Thing.opus", size=100),
        ]
        monkeypatch.setattr(
            "yubal_api.services.job_executor.CleanupService.find_orphans",
            lambda self: orphans,
        )

        added = [("New/Album/01 - Song Title.opus", "Song Title", "Artist")]
        should_complete = await executor._run_cleanup(
            "test-job", CancelToken(), None, added
        )

        assert should_complete is False
        assert store.transitions[-1] == ("test-job", JobStatus.AWAITING_REVIEW)
        pending = store.transition_kwargs[-1]["pending_orphans"]
        assert pending[0].replaced_by == added[0][0]
        assert pending[0].match_score is not None
        assert pending[1].replaced_by is None

    @pytest.mark.asyncio
    async def test_no_added_tracks_leaves_orphans_bare(
        self,
        executor: JobExecutor,
        store: FakeJobStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without added tracks, orphans are passed through unannotated."""
        orphans = [OrphanFile(path="Artist/Album/01 - Song Title.opus", size=100)]
        monkeypatch.setattr(
            "yubal_api.services.job_executor.CleanupService.find_orphans",
            lambda self: orphans,
        )

        should_complete = await executor._run_cleanup(
            "test-job", CancelToken(), None, None
        )

        assert should_complete is False
        pending = store.transition_kwargs[-1]["pending_orphans"]
        assert pending[0].replaced_by is None


class FakeGDrive:
    """Records delete_file_by_path calls; optionally reports missing or raises."""

    def __init__(self, *, found: bool = True, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self._found = found
        self._error = error

    def delete_file_by_path(self, relative_path: str) -> bool:
        self.calls.append(relative_path)
        if self._error is not None:
            raise self._error
        return self._found


class TestResolveOrphans:
    """Tests for orphan review resolution, including Drive mirroring."""

    SONG = "Artist/Album/01 - Song Title.opus"
    LYRICS = "Artist/Album/01 - Song Title.lrc"

    @pytest.fixture
    def store(self) -> FakeJobStore:
        store = FakeJobStore()
        store.job = Job(
            id="test-job",
            url="",
            audio_format=AudioCodec.OPUS,
            status=JobStatus.AWAITING_REVIEW,
        )
        return store

    @pytest.fixture
    def executor(self, store: FakeJobStore, tmp_path: Any) -> JobExecutor:
        for rel in (self.SONG, self.LYRICS):
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"audio")
        return JobExecutor(job_store=store, base_path=tmp_path)

    @staticmethod
    def _delete_decisions() -> list[dict[str, str]]:
        return [
            {"path": TestResolveOrphans.SONG, "action": "delete"},
            {"path": TestResolveOrphans.LYRICS, "action": "delete"},
        ]

    def test_deletes_locally_when_drive_disabled(
        self, executor: JobExecutor, store: FakeJobStore, tmp_path: Any
    ) -> None:
        """Without Drive configured, local deletion and completion still happen."""
        assert executor._gdrive_service is None

        assert executor.resolve_orphans("test-job", self._delete_decisions()) is True

        assert not (tmp_path / self.SONG).exists()
        assert not (tmp_path / self.LYRICS).exists()
        assert store.transitions[-1] == ("test-job", JobStatus.COMPLETED)

    def test_deletes_from_drive_with_relative_paths(
        self, executor: JobExecutor, store: FakeJobStore, tmp_path: Any
    ) -> None:
        """Each deleted file is removed from Drive by its library-relative path."""
        fake = FakeGDrive()
        executor._gdrive_service = fake  # type: ignore[assignment]

        assert executor.resolve_orphans("test-job", self._delete_decisions()) is True

        assert fake.calls == [self.SONG, self.LYRICS]
        assert not (tmp_path / self.SONG).exists()
        assert store.transitions[-1] == ("test-job", JobStatus.COMPLETED)

    def test_missing_on_drive_is_not_an_error(
        self, executor: JobExecutor, store: FakeJobStore
    ) -> None:
        """A file absent from Drive is a normal outcome, not a failure."""
        fake = FakeGDrive(found=False)
        executor._gdrive_service = fake  # type: ignore[assignment]

        assert executor.resolve_orphans("test-job", self._delete_decisions()) is True

        assert fake.calls == [self.SONG, self.LYRICS]
        assert store.transitions[-1] == ("test-job", JobStatus.COMPLETED)

    def test_drive_failure_does_not_block_completion(
        self, executor: JobExecutor, store: FakeJobStore, tmp_path: Any
    ) -> None:
        """A raising Drive call is logged; remaining files and the job proceed."""
        fake = FakeGDrive(error=RuntimeError("drive unavailable"))
        executor._gdrive_service = fake  # type: ignore[assignment]

        assert executor.resolve_orphans("test-job", self._delete_decisions()) is True

        assert fake.calls == [self.SONG, self.LYRICS]
        assert not (tmp_path / self.SONG).exists()
        assert not (tmp_path / self.LYRICS).exists()
        assert store.transitions[-1] == ("test-job", JobStatus.COMPLETED)

    def test_drive_untouched_without_delete_decisions(
        self, executor: JobExecutor, store: FakeJobStore, tmp_path: Any
    ) -> None:
        """Kept orphans reach neither the local unlink nor Drive."""
        fake = FakeGDrive()
        executor._gdrive_service = fake  # type: ignore[assignment]

        decisions = [
            {"path": self.SONG, "action": "keep"},
            {"path": self.LYRICS, "action": "never_delete"},
        ]
        assert executor.resolve_orphans("test-job", decisions) is True

        assert fake.calls == []
        assert (tmp_path / self.SONG).exists()
        assert store.transitions[-1] == ("test-job", JobStatus.COMPLETED)

    def test_wrong_status_resolves_nothing(
        self, executor: JobExecutor, store: FakeJobStore, tmp_path: Any
    ) -> None:
        """A job that is not awaiting review is left entirely alone."""
        assert store.job is not None
        store.job.status = JobStatus.COMPLETED
        fake = FakeGDrive()
        executor._gdrive_service = fake  # type: ignore[assignment]

        assert executor.resolve_orphans("test-job", self._delete_decisions()) is False

        assert fake.calls == []
        assert (tmp_path / self.SONG).exists()
