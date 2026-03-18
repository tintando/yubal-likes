"""Likes management API endpoints."""

import asyncio
import re

from fastapi import APIRouter, HTTPException

from yubal.client import YTMusicClient
from yubal.models.ytmusic import Thumbnail

from yubal_api.api.deps import (
    JobExecutorDep,
    LikesServiceDep,
    SettingsDep,
)
from yubal_api.schemas.likes import (
    DeleteFilesResponse,
    LikedSong,
    LikedSongsResponse,
    RedownloadResponse,
    UnlikeResponse,
)

router = APIRouter(prefix="/likes", tags=["likes"])


def _create_ytm_client(settings) -> YTMusicClient:
    cookies_path = settings.cookies_file if settings.cookies_file.exists() else None
    return YTMusicClient(cookies_path=cookies_path)


def _best_thumbnail(thumbnails: list[Thumbnail], size: int = 226) -> str | None:
    """Pick the best thumbnail URL, preferring square, and upscale if possible."""
    if not thumbnails:
        return None
    square = [t for t in thumbnails if t.width == t.height]
    url = max(square, key=lambda t: t.width).url if square else thumbnails[-1].url
    return re.sub(r"=w\d+-h\d+", f"=w{size}-h{size}", url)


@router.get("")
async def list_liked_songs(settings: SettingsDep) -> LikedSongsResponse:
    """List all liked songs from YouTube Music."""
    client = _create_ytm_client(settings)
    playlist = await asyncio.to_thread(client.get_playlist, "LM")

    items = [
        LikedSong(
            video_id=track.video_id,
            title=track.title,
            artists=[a.name for a in track.artists],
            album=track.album.name if track.album else None,
            thumbnail_url=_best_thumbnail(track.thumbnails),
            duration_seconds=track.duration_seconds,
        )
        for track in playlist.tracks
    ]

    return LikedSongsResponse(items=items, total=len(items))


@router.post("/{video_id}/unlike")
async def unlike_song(video_id: str, settings: SettingsDep) -> UnlikeResponse:
    """Remove a song from YouTube Music liked songs."""
    client = _create_ytm_client(settings)
    await asyncio.to_thread(client.rate_song, video_id, "INDIFFERENT")
    return UnlikeResponse()


@router.post("/{video_id}/delete")
async def delete_song_files(
    video_id: str, likes_service: LikesServiceDep
) -> DeleteFilesResponse:
    """Delete local and Drive files for a song."""
    deleted, relative_paths = await asyncio.to_thread(
        likes_service.delete_local_files, video_id
    )
    drive_deleted = await asyncio.to_thread(
        likes_service.delete_drive_files, relative_paths
    )
    return DeleteFilesResponse(files_deleted=deleted, drive_files_deleted=drive_deleted)


@router.post("/{video_id}/redownload")
async def redownload_song(
    video_id: str,
    likes_service: LikesServiceDep,
    job_executor: JobExecutorDep,
) -> RedownloadResponse:
    """Redownload a song by deleting local files and creating a new sync job."""
    await asyncio.to_thread(likes_service.delete_local_files, video_id)
    job = job_executor.create_and_start_job(
        url=f"https://music.youtube.com/watch?v={video_id}"
    )
    if job is None:
        raise HTTPException(status_code=409, detail="Job queue is full")
    return RedownloadResponse(job_id=job.id)
