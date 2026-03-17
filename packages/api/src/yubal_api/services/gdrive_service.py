"""Google Drive upload service for mirroring downloaded music."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from yubal import CancelToken

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_MIME = "application/vnd.google-apps.folder"


@dataclass(frozen=True, slots=True)
class GDriveUploadResult:
    """Result of a directory upload to Google Drive."""

    files_uploaded: int = 0
    files_skipped: int = 0
    bytes_uploaded: int = 0


@dataclass(frozen=True, slots=True)
class GDriveStatus:
    """Connection status for Google Drive."""

    connected: bool
    error: str | None = None


ProgressCallback = Callable[[int, int, str], None]


class GDriveService:
    """Wraps Google Drive API for uploading directory trees."""

    def __init__(self, token_file: Path, root_folder_id: str) -> None:
        self._token_file = token_file
        self._root_folder_id = root_folder_id
        self._folder_cache: dict[str, str] = {}

    def _build_service(self):
        credentials = Credentials.from_authorized_user_file(
            str(self._token_file), scopes=SCOPES
        )
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_credentials(credentials)
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    def _save_credentials(self, credentials: Credentials) -> None:
        """Persist updated token to disk."""
        import json

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
        }
        self._token_file.write_text(json.dumps(token_data))

    def check_connection(self) -> GDriveStatus:
        """Test Drive API connectivity."""
        try:
            service = self._build_service()
            service.files().get(fileId=self._root_folder_id, fields="id,name").execute()
            return GDriveStatus(connected=True)
        except Exception as e:
            return GDriveStatus(connected=False, error=str(e))

    def upload_directory(
        self,
        local_path: Path,
        cancel_token: CancelToken,
        on_progress: ProgressCallback | None = None,
    ) -> GDriveUploadResult:
        """Upload a local directory tree to Google Drive, preserving folder structure.

        Args:
            local_path: Root of the local directory to upload.
            cancel_token: Token for cooperative cancellation.
            on_progress: Callback(current, total, filename) after each file.

        Returns:
            Upload statistics.
        """
        service = self._build_service()
        self._folder_cache.clear()

        # Collect all files to upload
        files = sorted(f for f in Path(local_path).rglob("*") if f.is_file())
        total = len(files)

        if total == 0:
            return GDriveUploadResult()

        logger.info(
            "Uploading %d files to Google Drive",
            total,
            extra={"phase": "uploading", "phase_num": 5},
        )

        uploaded = 0
        skipped = 0
        bytes_uploaded = 0

        for i, file_path in enumerate(files):
            if cancel_token.is_cancelled:
                logger.info("Drive upload cancelled at %d/%d", i, total)
                break

            rel = file_path.relative_to(local_path)
            parent_id = self._ensure_folder_chain(service, rel.parent)

            if self._file_exists(service, file_path.name, parent_id, file_path.stat().st_size):
                skipped += 1
                logger.info(
                    "Skipped (exists): %s", rel, extra={"current": i, "total": total}
                )
            else:
                logger.info(
                    "Uploading: %s", rel, extra={"current": i, "total": total}
                )
                self._upload_file(service, file_path, parent_id)
                uploaded += 1
                bytes_uploaded += file_path.stat().st_size

            if on_progress:
                on_progress(i + 1, total, file_path.name)

        result = GDriveUploadResult(
            files_uploaded=uploaded,
            files_skipped=skipped,
            bytes_uploaded=bytes_uploaded,
        )
        logger.info(
            "Upload complete",
            extra={
                "stats": {
                    "stats_type": "upload",
                    "success": uploaded,
                    "skipped_by_reason": {"file_exists": skipped},
                }
            },
        )
        return result

    def _ensure_folder_chain(self, service, rel_folder: Path) -> str:
        """Create (or find) nested folders under root, returning the leaf folder ID."""
        if str(rel_folder) == ".":
            return self._root_folder_id

        parts = rel_folder.parts
        current_id = self._root_folder_id
        path_so_far = ""

        for part in parts:
            path_so_far = f"{path_so_far}/{part}" if path_so_far else part
            if path_so_far in self._folder_cache:
                current_id = self._folder_cache[path_so_far]
                continue

            folder_id = self._find_folder(service, part, current_id)
            if folder_id is None:
                folder_id = self._create_folder(service, part, current_id)

            self._folder_cache[path_so_far] = folder_id
            current_id = folder_id

        return current_id

    @staticmethod
    def _find_folder(service, name: str, parent_id: str) -> str | None:
        """Find a folder by name under a parent."""
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{escaped}' and '{parent_id}' in parents "
            f"and mimeType = '{FOLDER_MIME}' and trashed = false"
        )
        resp = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    @staticmethod
    def _create_folder(service, name: str, parent_id: str) -> str:
        """Create a folder under a parent and return its ID."""
        metadata = {
            "name": name,
            "mimeType": FOLDER_MIME,
            "parents": [parent_id],
        }
        folder = service.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    @staticmethod
    def _file_exists(service, name: str, parent_id: str, local_size: int) -> bool:
        """Check if a file with the same name and size exists in the parent folder."""
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{escaped}' and '{parent_id}' in parents "
            f"and mimeType != '{FOLDER_MIME}' and trashed = false"
        )
        resp = (
            service.files().list(q=query, fields="files(id,size)", pageSize=1).execute()
        )
        files = resp.get("files", [])
        if not files:
            return False
        remote_size = int(files[0].get("size", 0))
        return remote_size == local_size

    @staticmethod
    def _upload_file(service, file_path: Path, parent_id: str) -> str:
        """Upload a single file and return its Drive file ID."""
        metadata = {
            "name": file_path.name,
            "parents": [parent_id],
        }
        media = MediaFileUpload(str(file_path), resumable=True)
        result = (
            service.files().create(body=metadata, media_body=media, fields="id").execute()
        )
        return result["id"]
