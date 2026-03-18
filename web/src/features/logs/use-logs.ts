import { useEffect, useRef, useState } from "react";
import type { LogEntry, LogLine } from "@/api/logs";

export type { LogLine } from "@/api/logs";

const SSE_URL = "/api/logs/sse";
const MAX_LOG_LINES = 1000;
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000] as const;

export interface UseLogsResult {
  lines: LogLine[];
  isOffline: boolean;
}

/**
 * SSE log streaming hook with exponential backoff reconnection.
 *
 * Features:
 * - Automatic reconnection with exponential backoff (1s, 2s, 4s, 8s, 16s max)
 * - Memory-bounded log buffer (MAX_LOG_LINES)
 * - Connection state tracking
 */
export function useLogs(): UseLogsResult {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [isOffline, setIsOffline] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const idCounterRef = useRef(0);

  useEffect(() => {
    let mounted = true;

    function connect() {
      // Clean up existing connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const eventSource = new EventSource(SSE_URL);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        if (!mounted) return;
        setIsOffline(false);
        reconnectAttemptRef.current = 0;
      };

      eventSource.onmessage = (event) => {
        if (!mounted) return;
        const entry = JSON.parse(event.data) as LogEntry;
        const line: LogLine = { id: String(idCounterRef.current++), entry };
        setLines((prev) => {
          // Collapse consecutive skipped upload entries (single progress line each).
          const isSkippedUpload =
            entry.entry_type === "progress" &&
            entry.event_type === "file_upload" &&
            entry.message.startsWith("Skipped");
          if (isSkippedUpload && prev.length > 0) {
            const last = prev[prev.length - 1]!;
            if (
              last.entry.entry_type === "progress" &&
              last.entry.event_type === "file_upload" &&
              last.entry.message.startsWith("Skipped")
            ) {
              const updated = [...prev];
              updated[updated.length - 1] = line;
              return updated;
            }
          }

          // Collapse consecutive skipped track entries to avoid log flooding.
          // Each skipped track produces two log lines:
          //   progress: "[N/M] Artist - Title"
          //   status:   "Skipped (file exists): '/path'"
          // When consecutive skips occur, replace the old pair with the new one.
          const isSkipped =
            entry.entry_type === "status" && entry.status === "skipped";
          if (isSkipped && prev.length >= 3) {
            // prev ends with: [..., old_progress, old_status, new_progress]
            const oldStatus = prev[prev.length - 2]!;
            const newProgress = prev[prev.length - 1]!;
            if (
              oldStatus.entry.entry_type === "status" &&
              oldStatus.entry.status === "skipped"
            ) {
              // Remove old_progress + old_status, keep new_progress + new status
              const updated = prev.slice(0, -3);
              updated.push(newProgress);
              updated.push(line);
              return updated;
            }
          }

          const newLines = [...prev, line];
          return newLines.length > MAX_LOG_LINES
            ? newLines.slice(-MAX_LOG_LINES)
            : newLines;
        });
      };

      eventSource.onerror = () => {
        if (!mounted) return;
        setIsOffline(true);
        eventSource.close();

        // Schedule reconnection with exponential backoff
        const delayIndex = Math.min(
          reconnectAttemptRef.current,
          RECONNECT_DELAYS.length - 1,
        );
        const delay = RECONNECT_DELAYS[delayIndex];
        reconnectAttemptRef.current++;

        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      mounted = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  return { lines, isOffline };
}
