"""Persistent set of file paths that should never be deleted during cleanup."""

import json
from pathlib import Path


class KeepList:
    """JSON-file-backed persistent set of relative paths to never delete."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: set[str] = set()
        self.load()

    def load(self) -> None:
        """Load entries from disk."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._entries = set(data) if isinstance(data, list) else set()
            except (json.JSONDecodeError, OSError):
                self._entries = set()

    def save(self) -> None:
        """Persist entries to disk."""
        self._path.write_text(
            json.dumps(sorted(self._entries), indent=2), encoding="utf-8"
        )

    def add(self, rel_path: str) -> None:
        """Add a relative path to the keep list and save."""
        self._entries.add(rel_path)
        self.save()

    def contains(self, rel_path: str) -> bool:
        """Check if a relative path is in the keep list."""
        return rel_path in self._entries
