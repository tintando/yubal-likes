"""Library API schemas."""

from datetime import datetime

from pydantic import BaseModel


class LibraryFile(BaseModel):
    path: str
    size: int
    modified_at: datetime | None = None
    has_lyrics: bool = False
    # False means no M3U references the file (it would show up as an orphan)
    in_playlist: bool = False


class LibrarySearchResponse(BaseModel):
    items: list[LibraryFile]
    total: int


class LibraryDeleteRequest(BaseModel):
    path: str


class LibraryDeleteResponse(BaseModel):
    files_deleted: list[str]
    drive_files_deleted: int
