export interface SyncHistory {
  id: string;
  source: string;
  status: string;
  track_count: number | null;
  tracks_added: number;
  tracks_failed: number;
  tracks_skipped: number;
  orphans_deleted: number;
  orphans_kept: number;
  audio_codec: string | null;
  audio_bitrate: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TrackEvent {
  id: string;
  sync_id: string | null;
  event: string;
  path: string;
  title: string | null;
  artist: string | null;
  created_at: string;
}

interface SyncListResponse {
  items: SyncHistory[];
  total: number;
}

interface SyncDetailResponse {
  sync: SyncHistory;
  track_events: TrackEvent[];
}

interface TrackEventListResponse {
  items: TrackEvent[];
  total: number;
}

const BASE = "/api";

async function fetchJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE}${url}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function listSyncs(
  limit = 20,
  offset = 0,
): Promise<{ items: SyncHistory[]; total: number }> {
  const data = await fetchJson<SyncListResponse>(
    `/history?limit=${limit}&offset=${offset}`,
  );
  return data ?? { items: [], total: 0 };
}

export async function getSyncDetail(
  syncId: string,
): Promise<SyncDetailResponse | null> {
  return fetchJson<SyncDetailResponse>(`/history/${syncId}`);
}

export async function listTrackEvents(
  event?: string,
  limit = 50,
  offset = 0,
): Promise<{ items: TrackEvent[]; total: number }> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (event) params.set("event", event);
  const data = await fetchJson<TrackEventListResponse>(`/tracks?${params}`);
  return data ?? { items: [], total: 0 };
}
