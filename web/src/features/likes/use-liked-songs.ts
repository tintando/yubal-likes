import {
  deleteSongFiles,
  fetchLikedSongs,
  type LikedSong,
  redownloadSong,
  unlikeSong,
} from "@/api/likes";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { useCallback, useEffect, useMemo, useState } from "react";

function scoreMatch(song: LikedSong, query: string): number {
  const q = query.toLowerCase();
  const title = song.title.toLowerCase();

  // Title matches (highest priority)
  if (title === q) return 100;
  if (title.startsWith(q)) return 90;
  if (title.split(/\s+/).some((w) => w.startsWith(q))) return 80;
  if (title.includes(q)) return 70;

  // Artist matches
  const artists = song.artists.map((a) => a.toLowerCase());
  if (artists.some((a) => a === q)) return 60;
  if (artists.some((a) => a.startsWith(q))) return 50;
  if (artists.some((a) => a.split(/\s+/).some((w) => w.startsWith(q)))) return 45;
  if (artists.some((a) => a.includes(q))) return 40;

  // Album matches (lowest priority)
  const album = song.album?.toLowerCase();
  if (album) {
    if (album === q) return 35;
    if (album.startsWith(q)) return 30;
    if (album.includes(q)) return 25;
  }

  return 0;
}

export function useLikedSongs() {
  const [songs, setSongs] = useState<LikedSong[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const fetchSongs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchLikedSongs();
      setSongs(data.items);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to fetch liked songs";
      setError(msg);
      showErrorToast("Likes", msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSongs();
  }, [fetchSongs]);

  const unlike = useCallback(async (videoId: string) => {
    try {
      await unlikeSong(videoId);
      setSongs((prev) => prev.filter((s) => s.video_id !== videoId));
      showSuccessToast("Likes", "Song removed from liked songs");
    } catch {
      showErrorToast("Likes", "Failed to unlike song");
    }
  }, []);

  const deleteFiles = useCallback(async (videoId: string) => {
    try {
      const result = await deleteSongFiles(videoId);
      const total = result.files_deleted + result.drive_files_deleted;
      showSuccessToast(
        "Likes",
        `Deleted ${result.files_deleted} local${result.drive_files_deleted ? ` + ${result.drive_files_deleted} Drive` : ""} file${total !== 1 ? "s" : ""}`,
      );
    } catch {
      showErrorToast("Likes", "Failed to delete files");
    }
  }, []);

  const redownload = useCallback(async (videoId: string) => {
    try {
      await redownloadSong(videoId);
      showSuccessToast("Likes", "Redownload job created");
    } catch {
      showErrorToast("Likes", "Failed to start redownload");
    }
  }, []);

  const filteredSongs = useMemo(() => {
    if (!searchQuery.trim()) return songs;
    return songs
      .map((s) => ({ song: s, score: scoreMatch(s, searchQuery) }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((x) => x.song);
  }, [songs, searchQuery]);

  return {
    songs: filteredSongs,
    totalCount: songs.length,
    isLoading,
    error,
    searchQuery,
    setSearchQuery,
    fetchSongs,
    unlike,
    deleteFiles,
    redownload,
  };
}
