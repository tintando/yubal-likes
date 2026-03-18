"""Google Drive upload service for mirroring downloaded music."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
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
        self._files_cache: dict[str, dict[str, int]] = {}

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

        Uses batch folder listing to check file existence in-memory instead of
        per-file API calls.

        Args:
            local_path: Root of the local directory to upload.
            cancel_token: Token for cooperative cancellation.
            on_progress: Callback(current, total, filename) after each file.

        Returns:
            Upload statistics.
        """
        service = self._build_service()
        self._folder_cache.clear()
        self._files_cache.clear()

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

        # Prefetch the entire remote tree so skip checks are instant
        logger.info("Indexing remote files...")
        self._prefetch_remote_tree(service, self._root_folder_id, "")
        logger.info(
            "Indexed %d remote folders",
            len(self._files_cache),
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
            local_size = file_path.stat().st_size

            # Folder contents already prefetched; fallback for newly created folders
            if parent_id not in self._files_cache:
                self._files_cache[parent_id] = self._list_folder_files(
                    service, parent_id
                )

            remote_size = self._files_cache[parent_id].get(file_path.name)
            if remote_size is not None and remote_size == local_size:
                skipped += 1
                logger.info(
                    "Skipped (exists): %s",
                    rel,
                    extra={
                        "current": i,
                        "total": total,
                        "event_type": "file_upload",
                    },
                )
            else:
                logger.info(
                    "Uploading: %s",
                    rel,
                    extra={
                        "current": i,
                        "total": total,
                        "event_type": "file_upload",
                    },
                )
                self._upload_file(service, file_path, parent_id)
                uploaded += 1
                bytes_uploaded += local_size
                # Update cache after upload
                self._files_cache[parent_id][file_path.name] = local_size

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

    def _prefetch_remote_tree(self, service, root_id: str, _path_prefix: str) -> None:
        """Fetch all remote folders and files in two flat queries, populating caches.

        Uses the drive.file scope property: all visible items were created by
        this app, so a scopeless 'trashed = false' query returns only our files.
        This replaces N recursive per-folder API calls with ~2-4 paginated calls.
        """
        # 1. Fetch ALL folders to build id->path mapping
        folders_by_id: dict[str, tuple[str, str | None]] = {}  # id -> (name, parent_id)
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=f"mimeType = '{FOLDER_MIME}' and trashed = false",
                    fields="nextPageToken, files(id, name, parents)",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                parent = f.get("parents", [None])[0]
                folders_by_id[f["id"]] = (f["name"], parent)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        # Build folder_id -> relative path (only folders under our root)
        folder_paths: dict[str, str] = {root_id: ""}

        def resolve_path(fid: str) -> str | None:
            if fid in folder_paths:
                return folder_paths[fid]
            if fid not in folders_by_id:
                return None
            name, parent_id = folders_by_id[fid]
            if parent_id is None:
                return None
            parent_path = resolve_path(parent_id)
            if parent_path is None:
                return None
            path = f"{parent_path}/{name}" if parent_path else name
            folder_paths[fid] = path
            return path

        for fid in folders_by_id:
            resolve_path(fid)

        # Populate _folder_cache with resolved paths
        for fid, path in folder_paths.items():
            if fid != root_id and path:
                self._folder_cache[path] = fid
            # Initialize empty files map for every known folder
            self._files_cache[fid] = {}

        # 2. Fetch ALL non-folder files in one flat query
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=f"mimeType != '{FOLDER_MIME}' and trashed = false",
                    fields="nextPageToken, files(name, size, parents)",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                parent = f.get("parents", [None])[0]
                if parent and parent in folder_paths:
                    if parent not in self._files_cache:
                        self._files_cache[parent] = {}
                    self._files_cache[parent][f["name"]] = int(f.get("size", 0))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    @staticmethod
    def _list_folder_files(service, parent_id: str) -> dict[str, int]:
        """List all files in a folder, returning {name: size} mapping."""
        files_map: dict[str, int] = {}
        query = f"'{parent_id}' in parents and mimeType != '{FOLDER_MIME}' and trashed = false"
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(name, size)",
                    pageSize=1000,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                files_map[f["name"]] = int(f.get("size", 0))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return files_map

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
    def find_file_in_folder(service, filename: str, parent_id: str) -> str | None:
        """Find a file by name in a folder, returning its file ID."""
        escaped = filename.replace("\\", "\\\\").replace("'", "\\'")
        query = (
            f"name = '{escaped}' and '{parent_id}' in parents "
            f"and mimeType != '{FOLDER_MIME}' and trashed = false"
        )
        resp = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
        files = resp.get("files", [])
        return files[0]["id"] if files else None

    @staticmethod
    def delete_file(service, file_id: str) -> None:
        """Delete a file by ID."""
        service.files().delete(fileId=file_id).execute()

    def delete_file_by_path(self, relative_path: str) -> bool:
        """Delete a file on Drive by its relative path.

        Returns True if the file was found and deleted.
        """
        service = self._build_service()
        rel = Path(relative_path)
        parent_id = self._ensure_folder_chain(service, rel.parent)
        file_id = self.find_file_in_folder(service, rel.name, parent_id)
        if file_id:
            self.delete_file(service, file_id)
            return True
        return False

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
