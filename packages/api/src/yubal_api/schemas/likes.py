"""Likes API schemas."""

from typing import Literal

from pydantic import BaseModel


class LikedSong(BaseModel):
    video_id: str
    title: str
    artists: list[str]
    album: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: int
    # "new": first time we've seen this like; "changed": YT mutated
    # title/artists since the last sync; "synced": no divergence.
    status: Literal["new", "changed", "synced"] = "synced"
    synced_title: str | None = None


class LikedSongsResponse(BaseModel):
    items: list[LikedSong]
    total: int


class UnlikeResponse(BaseModel):
    status: str = "ok"


class DeleteFilesResponse(BaseModel):
    files_deleted: int
    drive_files_deleted: int


class RedownloadResponse(BaseModel):
    job_id: str


class DismissChangeResponse(BaseModel):
    status: str = "ok"
