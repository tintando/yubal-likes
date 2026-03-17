"""Job execution orchestration service."""

import asyncio
import logging
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID

import shutil

from yubal import AudioCodec, CancelToken, cleanup_part_files

from yubal_api.db.history_repository import HistoryRepository
from yubal_api.db.keep_list_repository import KeepListRepository
from yubal_api.db.sync_history import SyncHistory
from yubal_api.db.track_event import TrackEvent
from yubal_api.domain.enums import JobSource, JobStatus, ProgressStep
from yubal_api.domain.job import ContentInfo, Job, OrphanFile
from yubal_api.services.cleanup_service import CleanupService
from yubal_api.services.gdrive_service import GDriveService
from yubal_api.services.protocols import JobExecutionStore
from yubal_api.services.subscription_service import SubscriptionService
from yubal_api.services.sync_service import SyncService

logger = logging.getLogger(__name__)

PROGRESS_COMPLETE = 100.0


class JobExecutor:
    """Orchestrates job execution lifecycle.

    This executor manages background job execution with proper cleanup and
    cancellation support. Jobs run in a thread pool to avoid blocking the
    async event loop during I/O-heavy operations (yt-dlp downloads).

    Key Responsibilities:
        - Background task lifecycle (creation, tracking, cleanup)
        - Cancellation via CancelToken registry
        - Timeout enforcement via asyncio.timeout
        - Job queue continuation (starts next pending job when one completes)
        - Progress callback wiring to update job store

    Architecture Notes:
        - Uses JobExecutionStore protocol for persistence (ISP compliance)
        - CancelToken is the single source of truth for cancellation
        - Tasks are tracked in a set to prevent garbage collection
    """

    def __init__(
        self,
        job_store: JobExecutionStore,
        base_path: Path,
        audio_format: AudioCodec = AudioCodec.OPUS,
        audio_quality: int = 0,
        cookies_path: Path | None = None,
        fetch_lyrics: bool = True,
        apply_replaygain: bool = False,
        ascii_filenames: bool = False,
        download_ugc: bool = False,
        subscription_service: SubscriptionService | None = None,
        cache_path: Path | None = None,
        job_timeout: float = 1800,
        gdrive_service: GDriveService | None = None,
        history_repository: HistoryRepository | None = None,
        keep_list_repository: KeepListRepository | None = None,
    ) -> None:
        """Initialize the job executor.

        Args:
            job_store: Store for job persistence (protocol-based for testability).
            base_path: Base directory for downloaded files.
            audio_format: Target audio format (opus, mp3, m4a).
            audio_quality: Audio quality (0 = best, 10 = worst).
            cookies_path: Optional path to cookies.txt for authenticated requests.
            fetch_lyrics: Whether to fetch lyrics from lrclib.net.
            apply_replaygain: Whether to apply ReplayGain tags using rsgain.
            ascii_filenames: Whether to transliterate unicode to ASCII in filenames.
            download_ugc: Whether to download UGC tracks to _Unofficial folder.
            subscription_service: Optional service to update subscription metadata.
            cache_path: Optional directory for extraction cache.
            job_timeout: Maximum execution time per job in seconds.
        """
        self._job_store = job_store
        self._base_path = base_path
        self._audio_format = audio_format
        self._audio_quality = audio_quality
        self._cookies_path = cookies_path
        self._fetch_lyrics = fetch_lyrics
        self._apply_replaygain = apply_replaygain
        self._ascii_filenames = ascii_filenames
        self._download_ugc = download_ugc
        self._subscription_service = subscription_service
        self._cache_path = cache_path
        self._job_timeout = job_timeout
        self._gdrive_service = gdrive_service
        self._history_repository = history_repository
        self._keep_list_repository = keep_list_repository

        # Track background tasks to prevent GC during execution
        self._background_tasks: set[asyncio.Task[Any]] = set()
        # Map job_id -> CancelToken for cancellation support
        self._cancel_tokens: dict[str, CancelToken] = {}
        # Map job_id -> sync history UUID for orphan resolution
        self._current_sync_ids: dict[str, UUID] = {}

    def create_and_start_job(
        self,
        url: str,
        max_items: int | None = None,
        source: JobSource = JobSource.MANUAL,
        subscription_id: UUID | None = None,
    ) -> Job | None:
        """Create a new job and start it if ready.

        This is the primary entry point for job creation. It handles:
        - Creating the job with proper audio format from settings
        - Starting the job if a slot is available

        Args:
            url: The URL to download content from.
            max_items: Maximum number of items to download (None for all).
            source: Source of the job (manual API call or scheduler).
            subscription_id: Optional subscription that triggered this job.

        Returns:
            The created Job, or None if queue is full.
        """
        result = self._job_store.create(
            url, self._audio_format, max_items, source, subscription_id
        )
        if result is None:
            return None

        job, should_start = result
        if should_start:
            self.start_job(job)

        return job

    def create_and_start_import_job(
        self,
        file_paths: list[Path],
    ) -> Job | None:
        """Create an import job for local audio files.

        Args:
            file_paths: Paths to saved audio files in the temp directory.

        Returns:
            The created Job, or None if queue is full.
        """
        count = len(file_paths)
        result = self._job_store.create(
            f"import://{count}-files",
            self._audio_format,
            None,
            JobSource.IMPORT,
        )
        if result is None:
            return None

        job, should_start = result
        if should_start:
            self._start_import_job(job, file_paths)
        return job

    def _start_import_job(self, job: Job, file_paths: list[Path]) -> None:
        """Start an import job as a background task."""
        task = asyncio.create_task(
            self._run_import_job(job.id, file_paths),
            name=f"import-{job.id[:8]}",
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def start_job(self, job: Job) -> None:
        """Start a job as a background task.

        The task is tracked to prevent garbage collection and will
        automatically trigger the next pending job when complete.

        Args:
            job: The job to start executing.
        """
        task = asyncio.create_task(
            self._run_job(job.id, job.url, job.max_items, job.subscription_id),
            name=f"job-{job.id[:8]}",  # Helpful for debugging
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def cancel_job(self, job_id: str) -> bool:
        """Signal cancellation for a running job.

        This sets the cancel token which will be checked during download.
        The actual job status update happens in _run_job when it detects
        the cancellation.

        Args:
            job_id: ID of the job to cancel.

        Returns:
            True if a cancel token existed (job was running), False otherwise.
        """
        token = self._cancel_tokens.get(job_id)
        if token is None:
            return False

        token.cancel()
        logger.info("Job cancellation requested: %s", job_id[:8])
        return True

    def cancel_all_jobs(self) -> int:
        """Cancel all running jobs. Used during shutdown.

        Returns:
            Number of jobs that were signalled for cancellation.
        """
        tokens = list(self._cancel_tokens.values())
        for token in tokens:
            token.cancel()
        return len(tokens)

    async def _run_job(
        self,
        job_id: str,
        url: str,
        max_items: int | None = None,
        subscription_id: UUID | None = None,
    ) -> None:
        """Background task that runs the sync operation."""
        cancel_token = CancelToken()
        self._cancel_tokens[job_id] = cancel_token
        started_at = datetime.now(UTC)
        # Collect added tracks during download for history recording
        added_tracks: list[tuple[str, str | None, str | None]] = []

        try:
            # Check cancellation before starting (CancelToken is single source of truth)
            if cancel_token.is_cancelled:
                return

            async with asyncio.timeout(self._job_timeout):
                self._job_store.transition(
                    job_id,
                    JobStatus.FETCHING_INFO,
                    started_at=started_at,
                )

                # Create progress callback that updates job store
                loop = asyncio.get_running_loop()

                def on_progress(
                    step: ProgressStep,
                    _message: str,
                    progress: float | None,
                    details: dict[str, Any] | None,
                ) -> None:
                    if cancel_token.is_cancelled:
                        return

                    status = self._step_to_status(step)
                    content_info = (
                        self._parse_content_info(details) if details else None
                    )

                    # Collect track additions from download progress
                    if (
                        step == ProgressStep.DOWNLOADING
                        and details
                        and details.get("status") == "success"
                        and details.get("path")
                    ):
                        added_tracks.append((
                            details["path"],
                            details.get("track_title"),
                            details.get("track_artist"),
                        ))

                    # Skip terminal states - handled by result
                    if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                        return

                    loop.call_soon_threadsafe(
                        partial(
                            self._job_store.transition,
                            job_id,
                            status,
                            progress=progress,
                            content_info=content_info,
                        )
                    )

                # Run sync in thread pool
                sync_service = SyncService(
                    self._base_path,
                    self._audio_format,
                    self._cookies_path,
                    self._fetch_lyrics,
                    self._apply_replaygain,
                    self._ascii_filenames,
                    self._download_ugc,
                    self._cache_path,
                    self._audio_quality,
                )
                result = await asyncio.to_thread(
                    sync_service.run,
                    url,
                    on_progress,
                    cancel_token,
                    max_items,
                )

                # Handle result (cancelled status already set by cancel_job API)
                if cancel_token.is_cancelled:
                    pass  # Status already set, cleanup happens in finally block
                elif result.success:
                    # Update subscription metadata with latest info from YouTube Music
                    if (
                        self._subscription_service
                        and subscription_id
                        and result.content_info
                        and result.content_info.title
                    ):
                        self._subscription_service.update(
                            subscription_id,
                            {
                                "name": result.content_info.title,
                                "thumbnail_url": result.content_info.thumbnail_url,
                            },
                        )
                else:
                    error_msg = result.error or "Unknown error"
                    logger.error("Job %s failed: %s", job_id[:8], error_msg)
                    self._job_store.transition(job_id, JobStatus.FAILED)

            # Upload to Drive runs outside timeout context
            if (
                result.success
                and not cancel_token.is_cancelled
                and self._gdrive_service
            ):
                await self._upload_to_drive(
                    job_id, self._base_path, cancel_token, result.content_info
                )

            # Run orphan cleanup after upload, before COMPLETED
            should_complete = True
            if result.success and not cancel_token.is_cancelled:
                should_complete = await self._run_cleanup(
                    job_id, cancel_token, result.content_info
                )

            # Transition to COMPLETED after cleanup (or if no cleanup needed)
            if result.success and not cancel_token.is_cancelled and should_complete:
                self._job_store.transition(
                    job_id,
                    JobStatus.COMPLETED,
                    progress=PROGRESS_COMPLETE,
                    content_info=result.content_info,
                    download_stats=result.download_stats,
                )

            # Record sync history
            if self._history_repository:
                self._record_history(
                    job_id=job_id,
                    result=result,
                    started_at=started_at,
                    added_tracks=added_tracks,
                    cancel_token=cancel_token,
                    job_source=str(
                        self._job_store.get(job_id).source
                        if hasattr(self._job_store, "get")
                        and self._job_store.get(job_id)
                        else "manual"
                    ),
                )

        except TimeoutError:
            logger.warning(
                "Job %s timed out after %d seconds", job_id[:8], self._job_timeout
            )
            cancel_token.cancel()
            self._job_store.transition(job_id, JobStatus.FAILED)

        except Exception as e:
            logger.exception("Job %s failed with error: %s", job_id[:8], e)
            self._job_store.transition(job_id, JobStatus.FAILED)

        finally:
            # Clean up .part files if job was cancelled
            if cancel_token.is_cancelled:
                cleaned = cleanup_part_files(self._base_path)
                if cleaned:
                    logger.info("Cleaned up %d partial download(s)", cleaned)

            self._cancel_tokens.pop(job_id, None)
            self._current_sync_ids.pop(job_id, None)

            # Release active job slot AFTER cleanup, then start next
            # This ensures no concurrent downloads
            self._job_store.release_active(job_id)
            self._start_next_pending()

    async def _run_import_job(
        self,
        job_id: str,
        file_paths: list[Path],
    ) -> None:
        """Background task that runs the file import operation."""
        cancel_token = CancelToken()
        self._cancel_tokens[job_id] = cancel_token
        started_at = datetime.now(UTC)
        tmp_dir = file_paths[0].parent if file_paths else None

        try:
            if cancel_token.is_cancelled:
                return

            async with asyncio.timeout(self._job_timeout):
                self._job_store.transition(
                    job_id,
                    JobStatus.DOWNLOADING,
                    started_at=started_at,
                    content_info=ContentInfo(
                        title=f"Import ({len(file_paths)} files)",
                        artist="Local",
                        track_count=len(file_paths),
                    ),
                )

                loop = asyncio.get_running_loop()

                def on_progress(current: int, total: int, title: str) -> None:
                    if cancel_token.is_cancelled:
                        return
                    progress = (current / total * 100.0) if total > 0 else 0.0
                    loop.call_soon_threadsafe(
                        partial(
                            self._job_store.transition,
                            job_id,
                            JobStatus.DOWNLOADING,
                            progress=progress,
                        )
                    )

                from yubal.client import YTMusicClient
                from yubal.services.import_service import FileImportService

                client = YTMusicClient(cookies_path=self._cookies_path)
                import_service = FileImportService(
                    client=client,
                    base_path=self._base_path,
                    ascii_filenames=self._ascii_filenames,
                )

                result = await asyncio.to_thread(
                    import_service.import_files,
                    file_paths,
                    on_progress,
                    cancel_token,
                )

                if cancel_token.is_cancelled:
                    pass
                else:
                    from yubal.models.results import PhaseStats

                    stats = PhaseStats(
                        success=result.matched + result.unmatched,
                        failed=result.failed,
                        skipped=0,
                    )
                    self._job_store.transition(
                        job_id,
                        JobStatus.COMPLETED,
                        progress=PROGRESS_COMPLETE,
                        download_stats=stats,
                        content_info=ContentInfo(
                            title=f"Import ({len(file_paths)} files)",
                            artist="Local",
                            track_count=len(file_paths),
                        ),
                    )

        except TimeoutError:
            logger.warning(
                "Import job %s timed out after %d seconds",
                job_id[:8],
                self._job_timeout,
            )
            cancel_token.cancel()
            self._job_store.transition(job_id, JobStatus.FAILED)

        except Exception as e:
            logger.exception("Import job %s failed: %s", job_id[:8], e)
            self._job_store.transition(job_id, JobStatus.FAILED)

        finally:
            # Clean up temp directory
            if tmp_dir and tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

            self._cancel_tokens.pop(job_id, None)
            self._job_store.release_active(job_id)
            self._start_next_pending()

    def _record_history(
        self,
        job_id: str,
        result: Any,
        started_at: datetime,
        added_tracks: list[tuple[str, str | None, str | None]],
        cancel_token: CancelToken,
        job_source: str = "manual",
    ) -> None:
        """Record sync history and track events to database."""
        if not self._history_repository:
            return

        try:
            if cancel_token.is_cancelled:
                status = "cancelled"
            elif result.success:
                status = "completed"
            else:
                status = "failed"

            sync = SyncHistory(
                source=job_source,
                status=status,
                track_count=result.content_info.track_count if result.content_info else None,
                tracks_added=result.download_stats.success if result.download_stats else 0,
                tracks_failed=result.download_stats.failed if result.download_stats else 0,
                tracks_skipped=result.download_stats.skipped if result.download_stats else 0,
                audio_codec=result.content_info.audio_codec if result.content_info else None,
                audio_bitrate=result.content_info.audio_bitrate if result.content_info else None,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            sync = self._history_repository.record_sync(sync)

            # Record track addition events
            if added_tracks:
                events = [
                    TrackEvent(
                        sync_id=sync.id,
                        event="added",
                        path=path,
                        title=title,
                        artist=artist,
                    )
                    for path, title, artist in added_tracks
                ]
                self._history_repository.record_track_events(events)

            # Store sync_id on the job for orphan resolution to reference later
            self._current_sync_ids[job_id] = sync.id

        except Exception as e:
            logger.warning("Failed to record sync history: %s", e)

    async def _run_cleanup(
        self,
        job_id: str,
        cancel_token: CancelToken,
        content_info: ContentInfo | None,
    ) -> bool:
        """Run orphan file scan after sync. Returns True if job should complete immediately."""
        self._job_store.transition(
            job_id, JobStatus.CLEANING, progress=0.0, content_info=content_info
        )

        audio_ext = {f".{self._audio_format.value}"}
        cleanup = CleanupService(self._base_path, audio_ext)
        orphans = await asyncio.to_thread(cleanup.find_orphans)

        # Filter out keep-list entries (DB-backed or legacy JSON)
        if self._keep_list_repository:
            orphans = [o for o in orphans if not self._keep_list_repository.contains(o.path)]
        else:
            from yubal_api.services.keep_list import KeepList

            keep_list = KeepList(self._base_path / ".yubal_keep.json")
            orphans = [o for o in orphans if not keep_list.contains(o.path)]

        if orphans:
            self._job_store.transition(
                job_id,
                JobStatus.AWAITING_REVIEW,
                content_info=content_info,
                pending_orphans=orphans,
            )
            return False  # Job pauses here

        return True  # No orphans, can complete immediately

    def resolve_orphans(
        self,
        job_id: str,
        decisions: list[dict[str, str]],
    ) -> bool:
        """Process orphan review decisions and complete the job.

        Args:
            job_id: The job ID.
            decisions: List of {"path": ..., "action": "delete"|"keep"|"never_delete"}.

        Returns:
            True if resolved successfully.
        """
        job = self._job_store.get(job_id)
        if not job or job.status != JobStatus.AWAITING_REVIEW:
            return False

        audio_ext = {f".{self._audio_format.value}"}
        cleanup = CleanupService(self._base_path, audio_ext)

        to_delete: list[Path] = []
        to_keep_count = 0
        for decision in decisions:
            path = decision["path"]
            action = decision["action"]
            if action == "delete":
                to_delete.append(self._base_path / path)
            elif action == "never_delete":
                if self._keep_list_repository:
                    self._keep_list_repository.add(path)
                else:
                    from yubal_api.services.keep_list import KeepList

                    keep_list = KeepList(self._base_path / ".yubal_keep.json")
                    keep_list.add(path)
                to_keep_count += 1
            else:
                to_keep_count += 1

        if to_delete:
            result = cleanup.delete_files(to_delete)
            logger.info(
                "Orphan review cleanup: %d files deleted, %d bytes freed",
                result.files_deleted,
                result.bytes_freed,
            )

        # Record orphan events and update sync history
        sync_id = self._current_sync_ids.pop(job_id, None)
        if self._history_repository:
            try:
                # Record deleted track events
                if to_delete:
                    delete_events = [
                        TrackEvent(
                            sync_id=sync_id,
                            event="deleted",
                            path=str(p.relative_to(self._base_path)),
                        )
                        for p in to_delete
                    ]
                    self._history_repository.record_track_events(delete_events)

                # Update sync history with orphan counts
                if sync_id:
                    self._history_repository.update_sync(
                        sync_id,
                        orphans_deleted=len(to_delete),
                        orphans_kept=to_keep_count,
                    )
            except Exception as e:
                logger.warning("Failed to record orphan history: %s", e)

        self._job_store.transition(
            job_id,
            JobStatus.COMPLETED,
            progress=PROGRESS_COMPLETE,
            content_info=job.content_info,
            download_stats=job.download_stats,
            pending_orphans=None,
        )
        return True

    async def _upload_to_drive(
        self,
        job_id: str,
        destination: Path,
        cancel_token: CancelToken,
        content_info: ContentInfo | None,
    ) -> None:
        """Upload downloaded files to Google Drive."""
        assert self._gdrive_service is not None

        self._job_store.transition(
            job_id, JobStatus.UPLOADING, progress=0.0, content_info=content_info
        )

        loop = asyncio.get_running_loop()

        def on_progress(current: int, total: int, filename: str) -> None:
            if cancel_token.is_cancelled:
                return
            progress = (current / total * 100.0) if total > 0 else 0.0
            loop.call_soon_threadsafe(
                partial(
                    self._job_store.transition,
                    job_id,
                    JobStatus.UPLOADING,
                    progress=progress,
                )
            )

        try:
            result = await asyncio.to_thread(
                self._gdrive_service.upload_directory,
                destination,
                cancel_token,
                on_progress,
            )
            logger.info(
                "Drive upload for job %s: %d uploaded, %d skipped",
                job_id[:8],
                result.files_uploaded,
                result.files_skipped,
            )
        except Exception as e:
            # Drive upload failure shouldn't mark the job as failed
            logger.error("Drive upload failed for job %s: %s", job_id[:8], e)

    @staticmethod
    def _step_to_status(step: ProgressStep) -> JobStatus:
        """Map progress step to job status."""
        return {
            ProgressStep.FETCHING_INFO: JobStatus.FETCHING_INFO,
            ProgressStep.DOWNLOADING: JobStatus.DOWNLOADING,
            ProgressStep.IMPORTING: JobStatus.IMPORTING,
            ProgressStep.UPLOADING: JobStatus.UPLOADING,
            ProgressStep.CLEANING: JobStatus.CLEANING,
            ProgressStep.COMPLETED: JobStatus.COMPLETED,
            ProgressStep.FAILED: JobStatus.FAILED,
        }.get(step, JobStatus.DOWNLOADING)

    @staticmethod
    def _parse_content_info(details: dict[str, Any]) -> ContentInfo | None:
        """Extract content info from details dict."""
        if data := details.get("content_info"):
            try:
                return ContentInfo(**data)
            except (TypeError, ValueError) as e:
                logger.warning("Failed to parse content info: %s", e)
        return None

    def _start_next_pending(self) -> None:
        """Start the next pending job if any."""
        if next_job := self._job_store.pop_next_pending():
            self.start_job(next_job)
