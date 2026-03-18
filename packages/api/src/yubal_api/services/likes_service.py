"""Service for managing liked songs files."""

import logging
from pathlib import Path

from yubal import AudioCodec
from yubal.services.cache import ExtractionCache
from yubal.utils.filename import build_track_path

from yubal_api.services.gdrive_service import GDriveService

logger = logging.getLogger(__name__)


class LikesService:
    """Manages local and Drive files for liked songs."""

    def __init__(
        self,
        base_path: Path,
        audio_format: AudioCodec,
        cache_path: Path,
        gdrive_service: GDriveService | None = None,
    ) -> None:
        self._base_path = base_path
        self._audio_ext = f".{audio_format.value}"
        self._cache_path = cache_path
        self._gdrive = gdrive_service

    def find_local_files(self, video_id: str) -> list[Path]:
        """Find all local files associated with a video ID."""
        found: list[Path] = []

        # 1. Search _Unmatched and _Unofficial by video_id in filename
        for folder in ("_Unmatched", "_Unofficial"):
            folder_path = self._base_path / folder
            if folder_path.is_dir():
                for f in folder_path.glob(f"*[{video_id}].*"):
                    found.append(f)

        # 2. Search extraction cache for matched tracks
        cache = ExtractionCache(self._cache_path)
        with cache:
            metadata = cache.get(video_id)
            if metadata:
                track_path = build_track_path(
                    self._base_path,
                    metadata.primary_album_artist,
                    metadata.year,
                    metadata.album,
                    metadata.track_number,
                    metadata.title,
                )
                # Check audio file
                audio_file = track_path.with_suffix(self._audio_ext)
                if audio_file.exists():
                    found.append(audio_file)
                # Check companion .lrc file
                lrc_file = track_path.with_suffix(".lrc")
                if lrc_file.exists():
                    found.append(lrc_file)

                # Also check if the track has alternative video IDs in flat folders
                for alt_id in (metadata.atv_video_id, metadata.omv_video_id):
                    if alt_id and alt_id != video_id:
                        for folder in ("_Unmatched", "_Unofficial"):
                            folder_path = self._base_path / folder
                            if folder_path.is_dir():
                                for f in folder_path.glob(f"*[{alt_id}].*"):
                                    if f not in found:
                                        found.append(f)

        return found

    def delete_local_files(self, video_id: str) -> tuple[int, list[str]]:
        """Delete all local files for a video ID.

        Returns (count_deleted, list_of_relative_paths).
        """
        files = self.find_local_files(video_id)
        relative_paths: list[str] = []
        deleted = 0

        for f in files:
            try:
                rel = str(f.relative_to(self._base_path))
                relative_paths.append(rel)
                f.unlink()
                deleted += 1
                logger.info("Deleted: %s", rel)

                # Remove empty parent directories up to base
                parent = f.parent
                while parent != self._base_path:
                    try:
                        parent.rmdir()  # Only succeeds if empty
                        logger.info("Removed empty directory: %s", parent.name)
                        parent = parent.parent
                    except OSError:
                        break
            except Exception:
                logger.warning("Failed to delete %s", f, exc_info=True)

        # Remove from M3U playlists
        if relative_paths:
            self._clean_playlists(relative_paths)

        # Remove from extraction cache
        self._remove_from_cache(video_id)

        return deleted, relative_paths

    def delete_drive_files(self, relative_paths: list[str]) -> int:
        """Delete files from Google Drive by their relative paths."""
        if not self._gdrive or not relative_paths:
            return 0

        deleted = 0
        for rel_path in relative_paths:
            try:
                if self._gdrive.delete_file_by_path(rel_path):
                    deleted += 1
                    logger.info("Deleted from Drive: %s", rel_path)
            except Exception:
                logger.warning("Failed to delete from Drive: %s", rel_path, exc_info=True)

        return deleted

    def _clean_playlists(self, relative_paths: list[str]) -> None:
        """Remove references to deleted files from M3U playlists."""
        playlists_dir = self._base_path / "_Playlists"
        if not playlists_dir.is_dir():
            return

        for m3u in playlists_dir.glob("*.m3u"):
            try:
                lines = m3u.read_text(encoding="utf-8").splitlines()
                new_lines = [
                    line for line in lines
                    if not any(rel in line for rel in relative_paths)
                ]
                if len(new_lines) != len(lines):
                    m3u.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                    logger.info("Cleaned playlist: %s", m3u.name)
            except Exception:
                logger.warning("Failed to clean playlist %s", m3u.name, exc_info=True)

    def _remove_from_cache(self, video_id: str) -> None:
        """Remove a video ID from the extraction cache."""
        cache = ExtractionCache(self._cache_path)
        with cache:
            if cache._conn:
                cache._conn.execute(
                    "DELETE FROM cache WHERE video_id = ?", (video_id,)
                )
                cache._conn.execute(
                    "DELETE FROM unmatched WHERE video_id = ?", (video_id,)
                )
                cache._conn.commit()
