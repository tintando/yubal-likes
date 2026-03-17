"""Service for importing local audio files with YTM metadata enrichment."""

import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from mediafile import MediaFile

from yubal.client import YTMusicProtocol
from yubal.lib.matching import find_best_album_match
from yubal.models.cancel import CancelToken
from yubal.models.enums import MatchResult, VideoType
from yubal.models.track import TrackMetadata
from yubal.models.ytmusic import Artist
from yubal.services.tagging_service import AudioFileTaggingService
from yubal.utils.cover import crop_to_square, fetch_cover
from yubal.utils.filename import build_track_path, build_unmatched_track_path

logger = logging.getLogger(__name__)


@dataclass
class ImportFileResult:
    """Result of importing a single file."""

    source_path: str
    output_path: str | None = None
    matched: bool = False
    error: str | None = None


@dataclass
class ImportResult:
    """Result of importing multiple files."""

    total: int = 0
    matched: int = 0
    unmatched: int = 0
    failed: int = 0
    results: list[ImportFileResult] = field(default_factory=list)


class FileImportService:
    """Imports local audio files, enriching with YTM metadata when possible.

    For each file:
    1. Read existing metadata (title, artist, album, cover) via mediafile
    2. Search YTM for a match using "{artist} {title}"
    3. If matched: fetch album info, apply enriched tags, move to album folder
    4. If unmatched: keep original audio with cleaned tags, move to _Unmatched/
    """

    def __init__(
        self,
        client: YTMusicProtocol,
        base_path: Path,
        ascii_filenames: bool = False,
    ) -> None:
        self._client = client
        self._base_path = base_path
        self._ascii_filenames = ascii_filenames
        self._tagger = AudioFileTaggingService()

    def import_files(
        self,
        file_paths: list[Path],
        on_progress: callable | None = None,
        cancel_token: CancelToken | None = None,
    ) -> ImportResult:
        """Import local audio files with YTM metadata enrichment.

        Args:
            file_paths: List of audio file paths to import.
            on_progress: Optional callback(current, total, title).
            cancel_token: Optional cancellation token.

        Returns:
            ImportResult with counts and per-file results.
        """
        result = ImportResult(total=len(file_paths))

        for i, path in enumerate(file_paths):
            if cancel_token and cancel_token.is_cancelled:
                break

            file_result = self._import_single_file(path)
            result.results.append(file_result)

            if file_result.error:
                result.failed += 1
            elif file_result.matched:
                result.matched += 1
            else:
                result.unmatched += 1

            if on_progress:
                title = path.stem
                on_progress(i + 1, len(file_paths), title)

        return result

    def _import_single_file(self, path: Path) -> ImportFileResult:
        """Import a single audio file."""
        try:
            # Read existing metadata
            audio = MediaFile(path)
            title = audio.title or path.stem
            artist = audio.artist or "Unknown Artist"
            album = audio.album
            existing_cover = audio.images[0].data if audio.images else None

            # Search YTM
            query = f"{artist} {title}"
            logger.info("Importing '%s' — searching: %s", path.name, query)

            try:
                search_results = self._client.search_songs(query)
            except Exception as e:
                logger.warning("Search failed for '%s': %s", query, e)
                search_results = []

            # Try to match
            artists = [Artist(name=a.strip()) for a in artist.split("/")]
            match, _ = find_best_album_match(
                title, artists, search_results, VideoType.ATV.value
            )

            if match and match.title_match.is_good_match and match.artist_match.is_good_match:
                return self._import_matched(path, match, title, artist)
            else:
                return self._import_unmatched(
                    path, title, artist, album, existing_cover
                )

        except Exception as e:
            logger.exception("Failed to import '%s': %s", path.name, e)
            return ImportFileResult(source_path=str(path), error=str(e))

    def _import_matched(
        self,
        path: Path,
        match: object,
        title: str,
        artist: str,
    ) -> ImportFileResult:
        """Import a file that matched against YTM."""
        try:
            album = self._client.get_album(match.album_id)

            # Build enriched metadata
            track_meta = TrackMetadata(
                title=title,
                artists=[a.name for a in album.artists] if album.artists else [artist],
                album=album.title,
                album_artists=[a.name for a in album.artists],
                track_number=None,  # We don't know position in album
                total_tracks=len(album.tracks) if album.tracks else None,
                year=album.year,
                cover_url=self._get_best_thumbnail(album.thumbnails),
                match_result=MatchResult.MATCHED,
            )

            # Try to find track number by matching title to album tracks
            for at in album.tracks:
                if at.title.lower().strip() == title.lower().strip():
                    track_meta = track_meta.model_copy(
                        update={"track_number": at.track_number}
                    )
                    break

            # Fetch cover from album
            cover = fetch_cover(track_meta.cover_url)

            # Apply tags
            self._tagger.apply_metadata_tags(path, track_meta, cover)

            # Build destination path
            dest = build_track_path(
                base=self._base_path,
                artist=track_meta.primary_album_artist,
                year=track_meta.year,
                album=track_meta.album,
                track_number=track_meta.track_number,
                title=track_meta.title,
                ascii_filenames=self._ascii_filenames,
            )
            dest = Path(f"{dest}{path.suffix}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))

            logger.info("Imported (matched): '%s' → '%s'", path.name, dest)
            return ImportFileResult(
                source_path=str(path), output_path=str(dest), matched=True
            )

        except Exception as e:
            logger.exception("Failed matched import for '%s': %s", path.name, e)
            return ImportFileResult(source_path=str(path), error=str(e))

    def _import_unmatched(
        self,
        path: Path,
        title: str,
        artist: str,
        album: str | None,
        existing_cover: bytes | None,
    ) -> ImportFileResult:
        """Import a file that didn't match against YTM."""
        try:
            # Use truncated hash of filename for uniqueness (like video_id)
            file_hash = hashlib.sha256(path.name.encode()).hexdigest()[:11]

            track_meta = TrackMetadata(
                title=title,
                artists=[artist],
                album=album or title,
                album_artists=[artist],
                match_result=MatchResult.UNMATCHED,
            )

            # Crop existing cover if present
            cover = None
            if existing_cover:
                cover = crop_to_square(existing_cover)

            # Apply tags
            self._tagger.apply_metadata_tags(path, track_meta, cover)

            # Build destination path
            dest = build_unmatched_track_path(
                base=self._base_path,
                artist=track_meta.primary_album_artist,
                title=track_meta.title,
                video_id=file_hash,
                ascii_filenames=self._ascii_filenames,
            )
            dest = Path(f"{dest}{path.suffix}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))

            logger.info("Imported (unmatched): '%s' → '%s'", path.name, dest)
            return ImportFileResult(
                source_path=str(path), output_path=str(dest), matched=False
            )

        except Exception as e:
            logger.exception("Failed unmatched import for '%s': %s", path.name, e)
            return ImportFileResult(source_path=str(path), error=str(e))

    @staticmethod
    def _get_best_thumbnail(thumbnails: list) -> str | None:
        """Get the highest resolution thumbnail URL."""
        if not thumbnails:
            return None
        # Sort by width descending, pick largest
        return sorted(thumbnails, key=lambda t: t.width, reverse=True)[0].url
