"""ReplayGain scanner endpoints."""

from fastapi import APIRouter, HTTPException

from yubal_api.api.deps import ReplayGainScannerDep
from yubal_api.schemas.replaygain import ReplayGainScanResponse, ReplayGainStatusResponse

router = APIRouter(prefix="/replaygain", tags=["replaygain"])


@router.get("/status")
async def replaygain_status(scanner: ReplayGainScannerDep) -> ReplayGainStatusResponse:
    return ReplayGainStatusResponse(
        available=scanner.is_available,
        running=scanner.is_running,
        progress=scanner.progress,
        current_directory=scanner.current_directory,
    )


@router.post("/scan")
async def start_replaygain_scan(scanner: ReplayGainScannerDep) -> ReplayGainScanResponse:
    if not scanner.is_available:
        raise HTTPException(status_code=503, detail="rsgain is not installed")
    if scanner.is_running:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    scanner.start_scan()
    return ReplayGainScanResponse(status="started")
