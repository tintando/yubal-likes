import type { JobStatus } from "@/api/jobs";

/** Running states that indicate job is actively processing */
const RUNNING_STATUSES = new Set<JobStatus>([
  "fetching_info",
  "downloading",
  "importing",
  "uploading",
  "cleaning",
]);

/** Active states that indicate job is in progress (includes pending) */
const ACTIVE_STATUSES = new Set<JobStatus>(["pending", ...RUNNING_STATUSES]);

/** Check if a job status indicates the job is running (actively processing) */
export function isRunning(status: JobStatus): boolean {
  return RUNNING_STATUSES.has(status);
}

/** Check if a job status indicates the job is active (not finished) */
export function isActive(status: JobStatus): boolean {
  return ACTIVE_STATUSES.has(status);
}

/** Check if a job status indicates the job is finished */
export function isFinished(status: JobStatus): boolean {
  return !ACTIVE_STATUSES.has(status);
}
