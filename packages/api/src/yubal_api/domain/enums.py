from enum import StrEnum


class JobStatus(StrEnum):
    """Status of a background job."""

    PENDING = "pending"  # Waiting to start
    FETCHING_INFO = "fetching_info"  # Extracting content metadata
    DOWNLOADING = "downloading"  # Downloading tracks (0-80%)
    IMPORTING = "importing"  # Beets import (80-100%)
    UPLOADING = "uploading"  # Google Drive upload
    CLEANING = "cleaning"  # Orphan file cleanup
    AWAITING_REVIEW = "awaiting_review"  # Waiting for user to review orphans
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_finished(self) -> bool:
        return self in (self.COMPLETED, self.FAILED, self.CANCELLED)

    @property
    def is_active(self) -> bool:
        return not self.is_finished


class ProgressStep(StrEnum):
    """Steps in the sync workflow. Values match JobStatus."""

    FETCHING_INFO = "fetching_info"
    DOWNLOADING = "downloading"
    IMPORTING = "importing"
    UPLOADING = "uploading"
    CLEANING = "cleaning"
    COMPLETED = "completed"
    FAILED = "failed"


class JobSource(StrEnum):
    """Source of a background job."""

    MANUAL = "manual"
    SCHEDULER = "scheduler"
