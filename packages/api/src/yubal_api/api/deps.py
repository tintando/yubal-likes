"""FastAPI dependency injection factories.

This module provides type-safe dependency injection for FastAPI routes.
Dependencies are defined as Annotated types for clean, reusable injection.

Usage in routes:
    from yubal_api.api.deps import JobStoreDep, CookiesFileDep

    @router.get("/jobs")
    async def list_jobs(job_store: JobStoreDep) -> ...:
        ...
"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends

from yubal_api.api.container import Services, get_services
from yubal_api.db.history_repository import HistoryRepository
from yubal_api.db.keep_list_repository import KeepListRepository
from yubal_api.services.gdrive_service import GDriveService
from yubal_api.services.likes_service import LikesService
from yubal_api.services.replaygain_scanner import ReplayGainScanner
from yubal_api.services.job_event_bus import JobEventBus
from yubal_api.services.job_executor import JobExecutor
from yubal_api.services.job_store import JobStore
from yubal_api.services.log_buffer import LogBuffer
from yubal_api.services.playlist_info_service import PlaylistInfoService
from yubal_api.services.scheduler import Scheduler
from yubal_api.services.subscription_service import SubscriptionService
from yubal_api.settings import Settings, get_settings

# -- Settings --

SettingsDep = Annotated[Settings, Depends(get_settings)]

# -- Service dependencies (request-scoped via app.state) --

ServicesDep = Annotated[Services, Depends(get_services)]


def _get_job_store(services: ServicesDep) -> JobStore:
    """Get job store from services container."""
    return services.job_store


def _get_job_executor(services: ServicesDep) -> JobExecutor:
    """Get job executor from services container."""
    return services.job_executor


def _get_scheduler(services: ServicesDep) -> Scheduler:
    """Get scheduler from services container."""
    return services.scheduler


def _get_subscription_service(services: ServicesDep) -> SubscriptionService:
    """Get subscription service from services container."""
    return services.subscription_service


JobStoreDep = Annotated[JobStore, Depends(_get_job_store)]
JobExecutorDep = Annotated[JobExecutor, Depends(_get_job_executor)]
SchedulerDep = Annotated[Scheduler, Depends(_get_scheduler)]
SubscriptionServiceDep = Annotated[
    SubscriptionService, Depends(_get_subscription_service)
]


def _get_job_event_bus(services: ServicesDep) -> JobEventBus:
    """Get job event bus from services container."""
    return services.job_event_bus


def _get_log_buffer(services: ServicesDep) -> LogBuffer:
    """Get log buffer from services container."""
    return services.log_buffer


JobEventBusDep = Annotated[JobEventBus, Depends(_get_job_event_bus)]
LogBufferDep = Annotated[LogBuffer, Depends(_get_log_buffer)]

# -- Settings dependencies --

CookiesFileDep = Annotated[Path, Depends(lambda: get_settings().cookies_file)]
YtdlpDirDep = Annotated[Path, Depends(lambda: get_settings().ytdlp_dir)]


def _get_playlist_info_service() -> PlaylistInfoService:
    """Get playlist info service for fetching playlist metadata."""
    settings = get_settings()
    cookies_path = settings.cookies_file if settings.cookies_file.exists() else None
    return PlaylistInfoService(
        cookies_path=cookies_path, authuser=settings.get_authuser()
    )


PlaylistInfoServiceDep = Annotated[
    PlaylistInfoService, Depends(_get_playlist_info_service)
]


def _get_gdrive_service(services: ServicesDep) -> GDriveService | None:
    """Get Google Drive service from services container."""
    return services.gdrive_service


GDriveServiceDep = Annotated[GDriveService | None, Depends(_get_gdrive_service)]


def _get_replaygain_scanner(services: ServicesDep) -> ReplayGainScanner:
    return services.replaygain_scanner


ReplayGainScannerDep = Annotated[ReplayGainScanner, Depends(_get_replaygain_scanner)]


def _get_history_repository(services: ServicesDep) -> HistoryRepository:
    return services.history_repository


HistoryRepositoryDep = Annotated[HistoryRepository, Depends(_get_history_repository)]


def _get_keep_list_repository(services: ServicesDep) -> KeepListRepository:
    return services.keep_list_repository


KeepListRepositoryDep = Annotated[KeepListRepository, Depends(_get_keep_list_repository)]


def _get_likes_service(
    settings: SettingsDep, gdrive_service: GDriveServiceDep
) -> LikesService:
    return LikesService(
        base_path=settings.data,
        audio_format=settings.audio_format,
        cache_path=settings.cache_path,
        gdrive_service=gdrive_service,
    )


LikesServiceDep = Annotated[LikesService, Depends(_get_likes_service)]
