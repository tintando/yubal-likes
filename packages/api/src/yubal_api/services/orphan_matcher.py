"""Match orphaned files against freshly downloaded tracks.

When YouTube Music remaps a like to a new video_id (e.g. a re-release),
the next sync downloads the new file and the old one shows up as an
orphan. This module pairs orphans with tracks added in the same sync so
the review UI can suggest deleting the replaced file.

Pure functions only - no I/O.
"""

import re
from pathlib import PurePosixPath

from rapidfuzz import fuzz
from yubal.lib.matching import normalize_title

from yubal_api.domain.job import OrphanFile

# Minimum similarity (0-100) for an orphan/added-track pair to count as
# a replacement. False pair worst case: user unchecks a suggested delete.
MATCH_THRESHOLD = 75.0

_TRACK_PREFIX = re.compile(r"^\d+\s*[-–.]\s*")  # noqa: RUF001  # en dash intended
_VIDEO_ID_SUFFIX = re.compile(r"\s*\[[A-Za-z0-9_-]{11}\]$")
_FEAT_PAREN = re.compile(r"\s*[(\[]feat\.?.*?[)\]]", re.IGNORECASE)
_FEAT_TRAILING = re.compile(r"\s*\bft\.?\s+.*", re.IGNORECASE)


def normalize_stem(stem: str) -> str:
    """Normalize a filename stem for fuzzy comparison."""
    stem = _VIDEO_ID_SUFFIX.sub("", stem)
    stem = _TRACK_PREFIX.sub("", stem)
    stem = normalize_title(stem)
    stem = _FEAT_PAREN.sub("", stem)
    stem = _FEAT_TRAILING.sub("", stem)
    return re.sub(r"\s+", " ", stem).strip()


def _orphan_candidates(rel_path: str) -> list[str]:
    """Candidate comparison strings for an orphaned file path."""
    path = PurePosixPath(rel_path)
    candidates = [normalize_stem(path.stem)]
    # Album-tree paths (Artist/Album/NN - Title.ext) carry the artist in
    # the first component; special dirs like _Unmatched start with "_".
    parts = path.parts
    if len(parts) > 1 and not parts[0].startswith("_"):
        artist = parts[0].lower().strip()
        candidates.append(f"{artist} - {normalize_stem(path.stem)}")
    return candidates


def _added_candidates(
    rel_path: str, title: str | None, artist: str | None
) -> list[str]:
    """Candidate comparison strings for a freshly added track."""
    candidates = [normalize_stem(PurePosixPath(rel_path).stem)]
    if title:
        norm_title = normalize_stem(title)
        candidates.append(norm_title)
        if artist:
            candidates.append(f"{artist.lower().strip()} - {norm_title}")
    return candidates


def score_pair(orphan_candidates: list[str], added_candidates: list[str]) -> float:
    """Best similarity (0-100) across the candidate cross product.

    token_set_ratio is deliberately avoided - it over-matches remixes.
    """
    best = 0.0
    for o in orphan_candidates:
        for a in added_candidates:
            if not o or not a:
                continue
            best = max(best, fuzz.ratio(o, a), fuzz.token_sort_ratio(o, a))
    return best


def annotate_replacements(
    orphans: list[OrphanFile],
    added_tracks: list[tuple[str, str | None, str | None]],
    threshold: float = MATCH_THRESHOLD,
) -> list[OrphanFile]:
    """Mark orphans that look like they were replaced by an added track.

    Orphans are grouped by folder+stem so a .lrc inherits the match of its
    audio sibling. Pairs scoring >= threshold are assigned greedily 1:1
    (best score first, ties broken by path for determinism).
    """
    if not orphans or not added_tracks:
        return orphans

    # Group orphan indices by folder+stem; score on the audio file's path
    # (any non-.lrc member, else fall back to the first member).
    groups: dict[str, list[int]] = {}
    for i, orphan in enumerate(orphans):
        path = PurePosixPath(orphan.path)
        key = str(path.parent / path.stem)
        groups.setdefault(key, []).append(i)

    group_keys = sorted(groups)
    group_candidates: list[list[str]] = []
    for key in group_keys:
        members = groups[key]
        audio = next(
            (i for i in members if not orphans[i].path.lower().endswith(".lrc")),
            members[0],
        )
        group_candidates.append(_orphan_candidates(orphans[audio].path))

    added_candidates = [_added_candidates(*track) for track in added_tracks]

    pairs: list[tuple[float, str, str, int, int]] = []
    for gi, key in enumerate(group_keys):
        for ai, (added_path, _, _) in enumerate(added_tracks):
            score = score_pair(group_candidates[gi], added_candidates[ai])
            if score >= threshold:
                pairs.append((-score, key, added_path, gi, ai))
    pairs.sort()

    matched_groups: dict[int, tuple[str, float]] = {}
    used_added: set[int] = set()
    for neg_score, _, added_path, gi, ai in pairs:
        if gi in matched_groups or ai in used_added:
            continue
        matched_groups[gi] = (added_path, -neg_score)
        used_added.add(ai)

    result = list(orphans)
    for gi, (added_path, score) in matched_groups.items():
        for i in groups[group_keys[gi]]:
            result[i] = orphans[i].model_copy(
                update={"replaced_by": added_path, "match_score": score}
            )
    return result
