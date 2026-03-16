"""ReplayGain scanner schemas."""

from typing import Literal

from pydantic import BaseModel


class ReplayGainStatusResponse(BaseModel):
    available: bool
    running: bool
    progress: float | None = None
    current_directory: str | None = None


class ReplayGainScanResponse(BaseModel):
    status: Literal["started"]
