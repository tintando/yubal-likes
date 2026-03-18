"""File import API endpoints.

Handles uploading local audio files for metadata enrichment and organization.
"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, status

from yubal_api.api.deps import JobExecutorDep, SettingsDep
from yubal_api.api.exceptions import QueueFullError
from yubal_api.schemas.jobs import JobCreatedResponse

router = APIRouter(prefix="/imports", tags=["imports"])

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".flac", ".opus", ".ogg"}
MAX_FILES = 50
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid file upload"},
        409: {"description": "Queue is full"},
    },
)
async def import_files(
    files: list[UploadFile],
    job_executor: JobExecutorDep,
    settings: SettingsDep,
) -> JobCreatedResponse:
    """Upload and import local audio files.

    Files are validated, saved to a temp directory, then processed
    as an import job with YTM metadata enrichment.
    """
    from fastapi import HTTPException

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"Too many files (max {MAX_FILES})"
        )

    # Validate extensions
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

    # Save files to temp directory
    import_id = str(uuid.uuid4())
    tmp_dir = settings.data / "tmp" / "imports" / import_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    try:
        for f in files:
            dest = tmp_dir / (f.filename or f"file_{len(saved_paths)}")
            with dest.open("wb") as out:
                while chunk := await f.read(8192):
                    out.write(chunk)
                    # Check size
                    if dest.stat().st_size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File too large: {f.filename} (max 100MB)",
                        )
            saved_paths.append(dest)
    except Exception:
        # Clean up on failure
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    # Create import job
    job = job_executor.create_and_start_import_job(saved_paths)
    if job is None:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise QueueFullError()

    return JobCreatedResponse(id=job.id)
