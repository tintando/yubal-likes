export function formatTimeAgo(dateString: string | null | undefined): string {
  if (!dateString) return "Never";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return "";
  return new Date(dateString).toLocaleString();
}

/** Short date format: "Mar 15, 2:30 PM" */
export function formatDateShort(dateString: string | null | undefined): string {
  if (!dateString) return "";
  return new Date(dateString).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Format a duration in seconds to a human-readable string like "1m 23s" or "2h 5m" */
export function formatDuration(
  startDate: string | null | undefined,
  endDate: string | null | undefined,
): string {
  if (!startDate || !endDate) return "";
  const ms = new Date(endDate).getTime() - new Date(startDate).getTime();
  if (ms < 0) return "";
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return remainMins > 0 ? `${hours}h ${remainMins}m` : `${hours}h`;
}

export function formatCountdown(targetDate: Date | null): string {
  if (!targetDate) return "—";

  const ms = targetDate.getTime() - Date.now();

  if (ms <= 0) return "0";

  const totalSeconds = Math.floor(ms / 1000);
  const days = Math.floor(totalSeconds / 86400);

  if (days >= 1) {
    return `${days} day${days === 1 ? "" : "s"}`;
  }

  const hours = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  const pad = (n: number) => n.toString().padStart(2, "0");

  if (hours > 0) {
    return `${hours}:${pad(mins)}:${pad(secs)}`;
  }
  return `${mins}:${pad(secs)}`;
}
