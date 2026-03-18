"""Likes API schemas."""

from pydantic import BaseModel


class LikedSong(BaseModel):
    video_id: str
    title: str
    artists: list[str]
    album: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: int


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
