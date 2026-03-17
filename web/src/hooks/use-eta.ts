import { useEffect, useState } from "react";

/**
 * Estimates remaining time based on elapsed progress.
 * Returns a formatted string like "~2m 30s" or null if insufficient data.
 */
export function useEta(
  startedAt: string | null | undefined,
  progress: number,
): string | null {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!startedAt || progress <= 2 || progress >= 100) return;

    const interval = setInterval(() => {
      setTick((t) => t + 1);
    }, 5000);

    return () => clearInterval(interval);
  }, [startedAt, progress]);

  if (!startedAt || progress <= 2 || progress >= 100) return null;

  const elapsed = (Date.now() - new Date(startedAt).getTime()) / 1000;
  if (elapsed <= 0) return null;

  const rate = progress / elapsed;
  if (rate <= 0) return null;

  const remaining = (100 - progress) / rate;
  const mins = Math.floor(remaining / 60);
  const secs = Math.floor(remaining % 60);

  if (mins > 0) {
    return `~${mins}m ${secs}s`;
  }
  return `~${secs}s`;
}
