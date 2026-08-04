"""Tests for ExtractionCache, including unmatched cache."""

import time
from unittest.mock import patch

from yubal.models.enums import MatchResult, VideoType
from yubal.models.track import TrackMetadata
from yubal.services.cache import ExtractionCache


class TestExtractionCacheUnmatched:
    """Tests for the unmatched track cache."""

    def test_is_unmatched_false_for_unknown(self, tmp_path):
        cache = ExtractionCache(tmp_path)
        with cache:
            assert cache.is_unmatched("unknown_id") is False

    def test_is_unmatched_true_after_add(self, tmp_path):
        cache = ExtractionCache(tmp_path)
        with cache:
            cache.add_unmatched("vid1", VideoType.ATV.value)
            assert cache.is_unmatched("vid1") is True

    def test_is_unmatched_false_after_expiry(self, tmp_path):
        cache = ExtractionCache(tmp_path, unmatched_expiry_days=1)
        with cache:
            cache.add_unmatched("vid1", VideoType.ATV.value)
            # Simulate time passing beyond expiry (1 day = 86400s)
            with patch("yubal.services.cache.time") as mock_time:
                mock_time.time.return_value = time.time() + 86401
                assert cache.is_unmatched("vid1") is False
                # Row should be deleted, so re-check without mock
            assert cache.is_unmatched("vid1") is False

    def test_no_cross_contamination_with_matched_cache(self, tmp_path):
        """Unmatched and matched caches are independent."""
        cache = ExtractionCache(tmp_path)
        with cache:
            # Add to unmatched
            cache.add_unmatched("vid1", VideoType.ATV.value)
            # Should not appear in matched cache
            assert cache.get("vid1") is None

            # Add a matched track
            metadata = TrackMetadata(
                source_video_id="vid2",
                omv_video_id=None,
                atv_video_id="vid2",
                title="Test",
                artists=["Artist"],
                album="Album",
                album_artists=["Artist"],
                track_number=1,
                total_tracks=10,
                year="2024",
                cover_url=None,
                video_type=VideoType.ATV,
                duration_seconds=200,
                match_result=MatchResult.MATCHED,
            )
            cache.add(metadata)
            # Should not appear in unmatched cache
            assert cache.is_unmatched("vid2") is False

    def test_add_unmatched_replaces_existing(self, tmp_path):
        """Adding same video_id again updates the timestamp."""
        cache = ExtractionCache(tmp_path, unmatched_expiry_days=1)
        with cache:
            cache.add_unmatched("vid1", VideoType.ATV.value)

            # Simulate almost-expired entry, then re-add
            with patch("yubal.services.cache.time") as mock_time:
                future = time.time() + 86000  # almost expired
                mock_time.time.return_value = future
                # Re-add refreshes the timestamp
                cache.add_unmatched("vid1", VideoType.OMV.value)

            # Should still be valid since we just re-added
            assert cache.is_unmatched("vid1") is True

    def test_unmatched_no_connection(self, tmp_path):
        """Methods return safely when connection is not open."""
        cache = ExtractionCache(tmp_path)
        assert cache.is_unmatched("vid1") is False
        cache.add_unmatched("vid1", VideoType.ATV.value)  # should not raise
