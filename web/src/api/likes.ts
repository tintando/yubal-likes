import { api } from "./client";
import type { components } from "./schema";

export type LikedSong = components["schemas"]["LikedSong"];
export type LikedSongsResponse = components["schemas"]["LikedSongsResponse"];

function extractErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error && typeof error === "object" && "message" in error) {
    return (error as { message: string }).message;
  }
  return fallback;
}

export async function fetchLikedSongs(): Promise<LikedSongsResponse> {
  const { data, error } = await api.GET("/api/likes");
  if (error) throw new Error(extractErrorMessage(error, "Failed to fetch liked songs"));
  return data;
}

export async function unlikeSong(videoId: string) {
  const { data, error } = await api.POST("/api/likes/{video_id}/unlike", {
    params: { path: { video_id: videoId } },
  });
  if (error) throw new Error(extractErrorMessage(error, "Failed to unlike song"));
  return data;
}

export async function deleteSongFiles(videoId: string) {
  const { data, error } = await api.POST("/api/likes/{video_id}/delete", {
    params: { path: { video_id: videoId } },
  });
  if (error) throw new Error(extractErrorMessage(error, "Failed to delete files"));
  return data;
}

export async function redownloadSong(videoId: string) {
  const { data, error } = await api.POST("/api/likes/{video_id}/redownload", {
    params: { path: { video_id: videoId } },
  });
  if (error) throw new Error(extractErrorMessage(error, "Failed to redownload song"));
  return data;
}

export async function dismissChange(videoId: string) {
  const { data, error } = await api.POST("/api/likes/{video_id}/dismiss-change", {
    params: { path: { video_id: videoId } },
  });
  if (error) throw new Error(extractErrorMessage(error, "Failed to dismiss change"));
  return data;
}
