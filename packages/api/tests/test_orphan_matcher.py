"""Tests for the orphan replacement matcher (pure units)."""

from yubal_api.domain.job import OrphanFile
from yubal_api.services.orphan_matcher import (
    MATCH_THRESHOLD,
    annotate_replacements,
    normalize_stem,
    score_pair,
)


def orphan(path: str, size: int = 100) -> OrphanFile:
    return OrphanFile(path=path, size=size)


class TestNormalizeStem:
    def test_strips_track_prefix(self) -> None:
        assert normalize_stem("03 - Song Title") == "song title"

    def test_strips_video_id_suffix(self) -> None:
        assert normalize_stem("Song Title [dQw4w9WgXcQ]") == "song title"

    def test_keeps_non_video_id_brackets(self) -> None:
        # Only 11-char video-id-shaped brackets are stripped
        assert "[remix]" in normalize_stem("Song Title [remix]")

    def test_strips_feat_annotations(self) -> None:
        assert normalize_stem("Song (feat. Someone)") == "song"
        assert normalize_stem("Song ft. Someone") == "song"

    def test_strips_official_video_suffix(self) -> None:
        assert normalize_stem("Song Title (Official Video)") == "song title"

    def test_collapses_whitespace(self) -> None:
        assert normalize_stem("  Song   Title  ") == "song title"

    def test_combined(self) -> None:
        assert (
            normalize_stem("07 - Song Title (feat. X) [dQw4w9WgXcQ]") == "song title"
        )


class TestScorePair:
    def test_identical_scores_100(self) -> None:
        assert score_pair(["song title"], ["song title"]) == 100.0

    def test_cross_shape_match(self) -> None:
        # Album-tree orphan (artist prefix candidate) vs _Unmatched added
        # track named "Artist - Title"
        orphan_cands = ["song title", "artist - song title"]
        added_cands = ["artist - song title"]
        assert score_pair(orphan_cands, added_cands) == 100.0

    def test_unrelated_scores_low(self) -> None:
        assert (
            score_pair(["completely different"], ["nothing alike here"])
            < MATCH_THRESHOLD
        )

    def test_empty_candidates(self) -> None:
        assert score_pair([], ["a"]) == 0.0
        assert score_pair([""], ["a"]) == 0.0


class TestAnnotateReplacements:
    def test_empty_inputs_are_noops(self) -> None:
        orphans = [orphan("A/B/01 - Song.opus")]
        assert annotate_replacements([], [("x.opus", None, None)]) == []
        assert annotate_replacements(orphans, []) is orphans

    def test_basic_match(self) -> None:
        orphans = [orphan("Artist/Album/01 - Song Title.opus")]
        added = [("_Unmatched/Artist - Song Title [dQw4w9WgXcQ].opus", None, None)]

        result = annotate_replacements(orphans, added)

        assert result[0].replaced_by == added[0][0]
        assert result[0].match_score is not None
        assert result[0].match_score >= MATCH_THRESHOLD

    def test_lrc_inherits_group_match(self) -> None:
        orphans = [
            orphan("Artist/Album/01 - Song Title.opus"),
            orphan("Artist/Album/01 - Song Title.lrc"),
        ]
        added = [("Artist/Album2/01 - Song Title.opus", "Song Title", "Artist")]

        result = annotate_replacements(orphans, added)

        assert result[0].replaced_by == added[0][0]
        assert result[1].replaced_by == added[0][0]
        assert result[0].match_score == result[1].match_score

    def test_greedy_one_to_one(self) -> None:
        # Two orphans, one added track: only the better match is paired
        orphans = [
            orphan("A/X/01 - Song Title.opus"),
            orphan("A/X/02 - Song Title Remix Version.opus"),
        ]
        added = [("A/Y/01 - Song Title.opus", "Song Title", "A")]

        result = annotate_replacements(orphans, added)

        matched = [o for o in result if o.replaced_by]
        assert len(matched) == 1
        assert matched[0].path == "A/X/01 - Song Title.opus"

    def test_threshold_rejects_weak_pairs(self) -> None:
        orphans = [orphan("Artist/Album/01 - Completely Different.opus")]
        added = [("X/Y/Nothing Alike Here.opus", "Nothing Alike Here", "Z")]

        result = annotate_replacements(orphans, added)

        assert result[0].replaced_by is None
        assert result[0].match_score is None

    def test_unmatched_orphan_untouched(self) -> None:
        orphans = [
            orphan("Artist/Album/01 - Song Title.opus"),
            orphan("Other/Album/05 - Unrelated Thing.opus"),
        ]
        added = [("New/Album/01 - Song Title.opus", "Song Title", "Artist")]

        result = annotate_replacements(orphans, added)

        assert result[0].replaced_by == added[0][0]
        assert result[1].replaced_by is None

    def test_deterministic_tie_break(self) -> None:
        # Two identical-scoring orphans against one track: the
        # lexicographically smaller group path wins, every time.
        orphans = [
            orphan("B/Album/01 - Song Title.opus"),
            orphan("A/Album/01 - Song Title.opus"),
        ]
        added = [("C/Album/01 - Song Title.opus", "Song Title", None)]

        for _ in range(5):
            result = annotate_replacements(orphans, added)
            matched = [o for o in result if o.replaced_by]
            assert len(matched) == 1
            assert matched[0].path == "A/Album/01 - Song Title.opus"

    def test_match_uses_track_title_metadata(self) -> None:
        # Filename differs but the track title matches the orphan stem
        orphans = [orphan("Artist/Album/01 - My Great Song.opus")]
        added = [
            (
                "_Unofficial/Artist - My Great Song (Official Video).opus",
                "My Great Song (Official Video)",
                "Artist",
            )
        ]

        result = annotate_replacements(orphans, added)

        assert result[0].replaced_by == added[0][0]
