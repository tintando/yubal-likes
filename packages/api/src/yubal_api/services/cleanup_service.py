"""Orphan file cleanup service.

Deletes audio and LRC files not referenced by any M3U playlist.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of an orphan cleanup operation."""

    files_deleted: int = 0
    bytes_freed: int = 0
    dirs_removed: int = 0


class CleanupService:
    """Deletes audio files not referenced by any M3U playlist."""

    def __init__(self, base_path: Path, audio_extensions: set[str]) -> None:
        self._base_path = base_path
        self._audio_extensions = audio_extensions | {".lrc"}
        self._playlists_dir = base_path / "_Playlists"

    def cleanup_orphans(self) -> CleanupResult:
        """Find and delete files not referenced by any playlist."""
        logger.info(
            "Cleaning up orphaned files",
            extra={"phase": "cleaning", "phase_num": 6},
        )

        # 1. Collect all referenced files from M3U playlists
        referenced = self._collect_referenced_files()
        if not referenced:
            logger.info("No playlists found, skipping cleanup")
            return CleanupResult()

        # 2. Find orphaned files
        orphans = self._find_orphans(referenced)
        if not orphans:
            logger.info("No orphaned files found")
            return CleanupResult()

        # 3. Delete orphans
        result = self._delete_files(orphans)

        # 4. Remove empty directories
        result.dirs_removed = self._remove_empty_dirs()

        logger.info(
            "Cleanup complete",
            extra={
                "stats": {"stats_type": "cleanup", "success": result.files_deleted}
            },
        )
        return result

    def _collect_referenced_files(self) -> set[Path]:
        """Parse all .m3u files and collect referenced file paths."""
        referenced: set[Path] = set()

        if not self._playlists_dir.exists():
            return referenced

        for m3u in self._playlists_dir.glob("*.m3u"):
            for line in m3u.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                audio_path = (m3u.parent / line).resolve()
                referenced.add(audio_path)
                # Also mark companion .lrc as referenced
                lrc_path = audio_path.with_suffix(".lrc")
                referenced.add(lrc_path)

        return referenced

    def _find_orphans(self, referenced: set[Path]) -> list[Path]:
        """Walk base_path for audio/lrc files not in referenced set."""
        orphans: list[Path] = []

        for path in self._base_path.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self._audio_extensions:
                continue
            # Skip files inside _Playlists/
            try:
                path.relative_to(self._playlists_dir)
                continue
            except ValueError:
                pass
            if path.resolve() not in referenced:
                orphans.append(path)

        return orphans

    def _delete_files(self, orphans: list[Path]) -> CleanupResult:
        """Delete orphaned files with progress logging."""
        total = len(orphans)
        deleted = 0
        bytes_freed = 0

        for i, path in enumerate(orphans, 1):
            try:
                rel = path.relative_to(self._base_path)
            except ValueError:
                rel = path
            try:
                size = path.stat().st_size
                path.unlink()
                deleted += 1
                bytes_freed += size
                logger.info(
                    "Deleted: %s", rel, extra={"current": i, "total": total}
                )
            except OSError as e:
                logger.warning("Failed to delete %s: %s", rel, e)

        return CleanupResult(files_deleted=deleted, bytes_freed=bytes_freed)

    def _remove_empty_dirs(self) -> int:
        """Remove empty directories bottom-up."""
        removed = 0
        # Walk bottom-up by sorting by depth descending
        dirs = sorted(
            (d for d in self._base_path.rglob("*") if d.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        )
        for d in dirs:
            if d == self._playlists_dir:
                continue
            try:
                d.relative_to(self._playlists_dir)
                continue
            except ValueError:
                pass
            try:
                if not any(d.iterdir()):
                    d.rmdir()
                    removed += 1
            except OSError:
                pass
        return removed
