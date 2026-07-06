"""Tests for LibraryService search and delete."""

from pathlib import Path

import pytest
from yubal_api.services.library_service import LibraryService


@pytest.fixture
def library(tmp_path: Path) -> LibraryService:
    (tmp_path / "Artist" / "Album").mkdir(parents=True)
    (tmp_path / "Artist" / "Album" / "01 - Song Title.opus").write_bytes(b"x" * 10)
    (tmp_path / "Artist" / "Album" / "01 - Song Title.lrc").write_text("lyrics")
    (tmp_path / "_Unofficial").mkdir()
    (tmp_path / "_Unofficial" / "Someone - Other Tune [abcdefghijk].opus").write_bytes(
        b"y" * 20
    )
    (tmp_path / "_Playlists").mkdir()
    (tmp_path / "_Playlists" / "Liked.m3u").write_text(
        "../Artist/Album/01 - Song Title.opus\n", encoding="utf-8"
    )
    return LibraryService(tmp_path)


class TestSearch:
    def test_matches_all_words_case_insensitive(
        self, library: LibraryService
    ) -> None:
        results = library.search("song title")
        assert [f.path for f in results] == ["Artist/Album/01 - Song Title.opus"]

    def test_matches_folder_components(self, library: LibraryService) -> None:
        results = library.search("artist song")
        assert len(results) == 1

    def test_no_match(self, library: LibraryService) -> None:
        assert library.search("does not exist") == []

    def test_empty_query(self, library: LibraryService) -> None:
        assert library.search("   ") == []

    def test_flags(self, library: LibraryService) -> None:
        [in_pl] = library.search("song title")
        assert in_pl.in_playlist is True
        assert in_pl.has_lyrics is True

        [orphan] = library.search("other tune")
        assert orphan.in_playlist is False
        assert orphan.has_lyrics is False

    def test_lrc_not_listed_directly(self, library: LibraryService) -> None:
        # .lrc files are companions, not standalone results
        assert all(not f.path.endswith(".lrc") for f in library.search("song"))


class TestDeleteFile:
    def test_deletes_audio_lrc_and_playlist_entry(
        self, library: LibraryService, tmp_path: Path
    ) -> None:
        deleted, drive_deleted = library.delete_file(
            "Artist/Album/01 - Song Title.opus"
        )

        assert deleted == [
            "Artist/Album/01 - Song Title.opus",
            "Artist/Album/01 - Song Title.lrc",
        ]
        assert drive_deleted == 0
        assert not (tmp_path / "Artist").exists()  # empty dirs removed
        m3u = (tmp_path / "_Playlists" / "Liked.m3u").read_text()
        assert "Song Title" not in m3u

    def test_missing_file_raises(self, library: LibraryService) -> None:
        with pytest.raises(FileNotFoundError):
            library.delete_file("Artist/Album/99 - Nope.opus")

    def test_traversal_rejected(self, library: LibraryService) -> None:
        with pytest.raises(ValueError, match="escapes"):
            library.delete_file("../outside.opus")

    def test_non_audio_rejected(self, library: LibraryService) -> None:
        with pytest.raises(ValueError, match="audio"):
            library.delete_file("_Playlists/Liked.m3u")
