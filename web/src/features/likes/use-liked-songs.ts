import {
  deleteSongFiles,
  fetchLikedSongs,
  type LikedSong,
  redownloadSong,
  unlikeSong,
} from "@/api/likes";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { useCallback, useEffect, useMemo, useState } from "react";

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
    const q = searchQuery.toLowerCase();
    return songs.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.artists.some((a) => a.toLowerCase().includes(q)) ||
        (s.album && s.album.toLowerCase().includes(q)),
    );
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
