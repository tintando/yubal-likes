"""Local library management endpoints."""

import asyncio

from fastapi import APIRouter, HTTPException, Query

from yubal_api.api.deps import LibraryServiceDep
from yubal_api.schemas.library import (
    LibraryDeleteRequest,
    LibraryDeleteResponse,
    LibrarySearchResponse,
)

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/search")
async def search_library(
    library_service: LibraryServiceDep,
    q: str = Query(min_length=1),
) -> LibrarySearchResponse:
    """Search local audio files by name (all words must match)."""
    items = await asyncio.to_thread(library_service.search, q)
    return LibrarySearchResponse(items=items, total=len(items))


@router.post("/delete")
async def delete_library_file(
    body: LibraryDeleteRequest, library_service: LibraryServiceDep
) -> LibraryDeleteResponse:
    """Delete a local audio file (plus companion .lrc and Drive copies)."""
    try:
        deleted, drive_deleted = await asyncio.to_thread(
            library_service.delete_file, body.path
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return LibraryDeleteResponse(
        files_deleted=deleted, drive_files_deleted=drive_deleted
    )
