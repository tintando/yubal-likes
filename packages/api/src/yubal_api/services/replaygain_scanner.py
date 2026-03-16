"""Background ReplayGain scanner for the entire /data directory."""

import asyncio
import logging
import threading
from pathlib import Path

from yubal.config import AudioCodec
from yubal.services.replaygain import ReplayGainService

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS: dict[AudioCodec, str] = {
    AudioCodec.OPUS: ".opus",
    AudioCodec.MP3: ".mp3",
    AudioCodec.M4A: ".m4a",
}


class ReplayGainScanner:
    """Runs ReplayGain tagging across all directories in /data."""

    def __init__(self, base_path: Path, audio_format: AudioCodec) -> None:
        self._base_path = base_path
        self._audio_format = audio_format
        self._replaygain = ReplayGainService()
        self._running = False
        self._cancel = threading.Event()
        self._progress: float | None = None
        self._current_directory: str | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def is_available(self) -> bool:
        return self._replaygain.is_available()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def progress(self) -> float | None:
        return self._progress

    @property
    def current_directory(self) -> str | None:
        return self._current_directory

    def start_scan(self) -> None:
        if self._running:
            raise RuntimeError("Scan already running")
        self._cancel.clear()
        self._progress = 0.0
        self._current_directory = None
        self._task = asyncio.create_task(self._run_async())

    def cancel_scan(self) -> None:
        self._cancel.set()

    async def _run_async(self) -> None:
        try:
            await asyncio.to_thread(self._run_scan)
        except Exception:
            logger.exception("ReplayGain scan failed")
        finally:
            self._running = False
            self._progress = None
            self._current_directory = None

    def _run_scan(self) -> None:
        self._running = True
        ext = AUDIO_EXTENSIONS[self._audio_format]

        # Find all directories containing audio files
        dirs_with_audio: list[Path] = []
        for path in sorted(self._base_path.rglob(f"*{ext}")):
            parent = path.parent
            if parent not in dirs_with_audio:
                dirs_with_audio.append(parent)

        if not dirs_with_audio:
            logger.info("ReplayGain scan: no audio files found in %s", self._base_path)
            return

        total = len(dirs_with_audio)
        logger.info("ReplayGain scan: processing %d directories", total)

        for i, directory in enumerate(dirs_with_audio):
            if self._cancel.is_set():
                logger.info("ReplayGain scan cancelled")
                return

            rel = directory.relative_to(self._base_path)
            self._current_directory = str(rel)
            self._progress = (i / total) * 100

            files = sorted(directory.glob(f"*{ext}"))
            if files:
                logger.info("ReplayGain: scanning %s (%d files)", rel, len(files))
                self._replaygain.apply_replaygain(
                    files, self._audio_format, album_mode=True
                )

        self._progress = 100.0
        logger.info("ReplayGain scan complete")
