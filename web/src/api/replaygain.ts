import { api } from "./client";

export async function startReplayGainScan(): Promise<boolean> {
  const { error } = await api.POST("/replaygain/scan");
  return !error;
}

export async function getReplayGainStatus() {
  const { data, error } = await api.GET("/replaygain/status");
  if (error) return null;
  return data;
}
