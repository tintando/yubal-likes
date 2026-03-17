import type { Job } from "@/api/jobs";
import { EmptyState } from "@/components/common/empty-state";
import { Panel, PanelContent, PanelHeader } from "@/components/common/panel";
import { useEta } from "@/hooks/use-eta";
import { formatDateTime } from "@/lib/format";
import { isActive, isFinished, isRunning } from "@/lib/job-status";
import { Button, Progress, Tooltip } from "@heroui/react";
import {
  HistoryIcon,
  InboxIcon,
  RotateCwIcon,
  Trash2Icon,
  XIcon,
  ZapIcon,
} from "lucide-react";
import { STATUS_CONFIG, StatusIcon } from "./job-card";

type Props = {
  jobs: Job[];
  isLoading: boolean;
  onCancel: (jobId: string) => void;
  onDelete: (jobId: string) => void;
  onRetry: (jobId: string) => void;
};

function JobRow({
  job,
  onCancel,
  onDelete,
  onRetry,
}: {
  job: Job;
  onCancel?: (jobId: string) => void;
  onDelete?: (jobId: string) => void;
  onRetry?: (jobId: string) => void;
}) {
  const jobRunning = isRunning(job.status);
  const jobActive = isActive(job.status);
  const jobFinished = isFinished(job.status);
  const hasPartialFailures =
    job.status === "completed" && (job.download_stats?.failed ?? 0) > 0;
  const eta = useEta(job.started_at, job.progress);

  const trackCount = job.content_info?.track_count;
  const dateStr = job.created_at ? formatDateTime(job.created_at) : "";

  // Summary text
  let summary: string;
  if (jobRunning) {
    const phase = job.status.replace(/_/g, " ");
    summary = `${phase} ${Math.round(job.progress)}%`;
    if (eta) summary += ` ${eta}`;
  } else if (job.status === "awaiting_review") {
    const count = job.pending_orphans?.length ?? 0;
    summary = `${count} orphan${count !== 1 ? "s" : ""} to review`;
  } else if (job.status === "failed") {
    summary = "failed";
  } else if (job.status === "cancelled") {
    summary = "cancelled";
  } else if (job.status === "pending") {
    summary = "queued";
  } else if (trackCount) {
    summary = `${trackCount} track${trackCount !== 1 ? "s" : ""}`;
  } else {
    summary = "completed";
  }

  const opacity = job.status === "cancelled" ? "opacity-50" : "";

  return (
    <div className={`group ${opacity}`}>
      <div className="flex items-center gap-3 px-2 py-1.5">
        {/* Status icon */}
        <StatusIcon status={job.status} hasPartialFailures={hasPartialFailures} />

        {/* Date */}
        <span className="text-foreground-500 text-small shrink-0 font-mono">
          {dateStr}
        </span>

        {/* Summary */}
        <span className="text-foreground text-small min-w-0 flex-1 truncate font-mono">
          {summary}
        </span>

        {/* Auto chip */}
        {job.source === "scheduler" && (
          <Tooltip content="Synced by the scheduler" closeDelay={0}>
            <span className="text-tiny flex shrink-0 items-center gap-0.5 rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-sky-600 dark:bg-sky-500/20 dark:text-sky-300">
              <ZapIcon size={12} />
              Auto
            </span>
          </Tooltip>
        )}

        {/* Action buttons */}
        <div className="flex shrink-0 items-center gap-1">
          {jobActive && job.status !== "awaiting_review" && onCancel && (
            <Button
              variant="light"
              size="sm"
              isIconOnly
              className="text-foreground-500 hover:text-danger h-6 w-6 md:not-group-hover:hidden"
              onPress={() => onCancel(job.id)}
            >
              <XIcon className="h-3.5 w-3.5" />
            </Button>
          )}
          {job.status === "failed" && onRetry && (
            <Tooltip content="Retry" closeDelay={0}>
              <Button
                variant="light"
                size="sm"
                isIconOnly
                className="text-foreground-500 hover:text-primary h-6 w-6"
                onPress={() => onRetry(job.id)}
              >
                <RotateCwIcon className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
          )}
          {jobFinished && onDelete && (
            <Button
              variant="light"
              size="sm"
              isIconOnly
              className="text-foreground-500 hover:text-danger h-6 w-6 not-group-hover:hidden max-md:hidden"
              onPress={() => onDelete(job.id)}
            >
              <Trash2Icon className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Compact progress bar for running jobs */}
      {jobRunning && (
        <div className="px-2 pb-1">
          <Progress
            value={job.progress}
            size="sm"
            color={STATUS_CONFIG[job.status].progressColor}
            className="flex-1"
            classNames={{
              indicator: "transition-all duration-500 ease-out",
            }}
            aria-label="Job progress"
          />
        </div>
      )}
    </div>
  );
}

export function JobsPanel({ jobs, isLoading, onCancel, onDelete, onRetry }: Props) {
  return (
    <Panel>
      <PanelHeader
        leadingIcon={<HistoryIcon size={18} />}
        badge={
          jobs.length > 0 && (
            <span className="text-foreground-400 font-mono text-xs">
              ({jobs.length})
            </span>
          )
        }
      >
        Recent syncs
      </PanelHeader>
      <PanelContent height="h-80" className="space-y-0">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <span className="text-foreground-400 text-small font-mono">
              Loading...
            </span>
          </div>
        ) : jobs.length === 0 ? (
          <EmptyState icon={InboxIcon} title="No syncs yet" />
        ) : (
          <div className="divide-divider flex flex-col divide-y">
            {jobs.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                onCancel={isActive(job.status) ? onCancel : undefined}
                onDelete={!isActive(job.status) ? onDelete : undefined}
                onRetry={job.status === "failed" ? onRetry : undefined}
              />
            ))}
          </div>
        )}
      </PanelContent>
    </Panel>
  );
}
