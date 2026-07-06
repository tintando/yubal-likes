"""Service for searching and managing local library files."""

import logging
from datetime import UTC, datetime
from pathlib import Path

from yubal_api.schemas.library import LibraryFile
from yubal_api.services.gdrive_service import GDriveService

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".opus", ".mp3", ".m4a", ".flac", ".ogg", ".wav"}
MAX_RESULTS = 100


class LibraryService:
    """Searches and deletes audio files in the local data directory."""

    def __init__(
        self, base_path: Path, gdrive_service: GDriveService | None = None
    ) -> None:
        self._base_path = base_path
        self._gdrive = gdrive_service
        self._playlists_dir = base_path / "_Playlists"

    def search(self, query: str, limit: int = MAX_RESULTS) -> list[LibraryFile]:
        """Find audio files whose relative path contains all query words."""
        words = query.lower().split()
        if not words:
            return []

        referenced = self._collect_referenced_files()
        results: list[LibraryFile] = []

        for path in sorted(self._base_path.rglob("*")):
            if len(results) >= limit:
                break
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            if self._playlists_dir in path.parents:
                continue

            rel = str(path.relative_to(self._base_path))
            haystack = rel.lower()
            if not all(w in haystack for w in words):
                continue

            try:
                stat = path.stat()
                size = stat.st_size
                modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            except OSError:
                size = 0
                modified_at = None

            results.append(
                LibraryFile(
                    path=rel,
                    size=size,
                    modified_at=modified_at,
                    has_lyrics=path.with_suffix(".lrc").exists(),
                    in_playlist=path.resolve() in referenced,
                )
            )

        return results

    def delete_file(self, rel_path: str) -> tuple[list[str], int]:
        """Delete an audio file, its companion .lrc, and Drive copies.

        Returns (deleted relative paths, drive files deleted).

        Raises:
            ValueError: If the path escapes the library or isn't an audio file.
            FileNotFoundError: If the file doesn't exist.
        """
        target = (self._base_path / rel_path).resolve()
        if not target.is_relative_to(self._base_path.resolve()):
            raise ValueError("Path escapes the library directory")
        if target.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError("Not an audio file")
        if not target.is_file():
            raise FileNotFoundError(rel_path)

        deleted: list[str] = []
        for f in (target, target.with_suffix(".lrc")):
            if not f.is_file():
                continue
            rel = str(f.relative_to(self._base_path.resolve()))
            try:
                f.unlink()
                deleted.append(rel)
                logger.info("Deleted: %s", rel)
            except OSError:
                logger.warning("Failed to delete %s", rel, exc_info=True)

        self._clean_playlists(deleted)
        self._remove_empty_dirs(target.parent)

        drive_deleted = 0
        if self._gdrive:
            for rel in deleted:
                try:
                    if self._gdrive.delete_file_by_path(rel):
                        drive_deleted += 1
                        logger.info("Deleted from Drive: %s", rel)
                except Exception:
                    logger.warning(
                        "Failed to delete from Drive: %s", rel, exc_info=True
                    )

        return deleted, drive_deleted

    def _collect_referenced_files(self) -> set[Path]:
        """Parse all .m3u files and collect referenced file paths."""
        referenced: set[Path] = set()
        if not self._playlists_dir.exists():
            return referenced

        for m3u in self._playlists_dir.glob("*.m3u"):
            try:
                lines = m3u.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    referenced.add((m3u.parent / line).resolve())

        return referenced

    def _clean_playlists(self, relative_paths: list[str]) -> None:
        """Remove references to deleted files from M3U playlists."""
        if not relative_paths or not self._playlists_dir.is_dir():
            return

        for m3u in self._playlists_dir.glob("*.m3u"):
            try:
                lines = m3u.read_text(encoding="utf-8").splitlines()
                new_lines = [
                    line
                    for line in lines
                    if not any(rel in line for rel in relative_paths)
                ]
                if len(new_lines) != len(lines):
                    m3u.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                    logger.info("Cleaned playlist: %s", m3u.name)
            except OSError:
                logger.warning("Failed to clean playlist %s", m3u.name, exc_info=True)

    def _remove_empty_dirs(self, start: Path) -> None:
        """Remove empty directories from start up to (not including) base."""
        parent = start
        base = self._base_path.resolve()
        while parent != base and parent.is_relative_to(base):
            try:
                parent.rmdir()  # Only succeeds if empty
                logger.info("Removed empty directory: %s", parent.name)
            except OSError:
                break
            parent = parent.parent
