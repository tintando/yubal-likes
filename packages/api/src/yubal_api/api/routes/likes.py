"""Likes management API endpoints."""

import asyncio
import re
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
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

_thumbnail_urls: dict[str, str] = {}


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

    items = []
    for track in playlist.tracks:
        yt_url = _best_thumbnail(track.thumbnails)
        if yt_url:
            _thumbnail_urls[track.video_id] = yt_url
        items.append(
            LikedSong(
                video_id=track.video_id,
                title=track.title,
                artists=[a.name for a in track.artists],
                album=track.album.name if track.album else None,
                thumbnail_url=(
                    f"/api/likes/thumbnails/{track.video_id}"
                    if yt_url
                    else None
                ),
                duration_seconds=track.duration_seconds,
            )
        )

    return LikedSongsResponse(items=items, total=len(items))


def _fetch_and_cache_thumbnail(url: str, cache_file: Path) -> None:
    """Download a thumbnail from YouTube and save to disk."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, cache_file)


@router.get("/thumbnails/{video_id}")
async def get_thumbnail(video_id: str, settings: SettingsDep) -> FileResponse:
    """Serve a cached thumbnail, fetching from YouTube on first request."""
    cache_file = settings.thumbnails_path / f"{video_id}.jpg"

    if cache_file.exists():
        return FileResponse(
            cache_file,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    yt_url = _thumbnail_urls.get(video_id)
    if not yt_url:
        raise HTTPException(status_code=404, detail="Thumbnail URL not known")

    await asyncio.to_thread(_fetch_and_cache_thumbnail, yt_url, cache_file)

    return FileResponse(
        cache_file,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


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
    """Redownload a song by deleting local and Drive files and creating a new sync job."""
    deleted, relative_paths = await asyncio.to_thread(
        likes_service.delete_local_files, video_id
    )
    await asyncio.to_thread(likes_service.delete_drive_files, relative_paths)
    job = job_executor.create_and_start_job(
        url=f"https://music.youtube.com/watch?v={video_id}"
    )
    if job is None:
        raise HTTPException(status_code=409, detail="Job queue is full")
    return RedownloadResponse(job_id=job.id)
