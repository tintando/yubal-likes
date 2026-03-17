import { startReplayGainScan } from "@/api/replaygain";
import { getStatus } from "@/api/subscriptions";
import type { SchedulerStatus } from "@/api/subscriptions";
import { SubscriptionCard } from "@/features/subscriptions/subscription-card";
import { LogsPanel } from "@/features/logs/logs-panel";
import { JobsPanel } from "@/features/jobs/jobs-panel";
import { OrphanReview } from "@/features/jobs/orphan-review";
import { useJobs } from "@/features/jobs/jobs-context";
import { useScheduleCountdown } from "@/hooks/use-schedule-countdown";
import { useTimeAgo } from "@/hooks/use-time-ago";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { Button, Tooltip } from "@heroui/react";
import { ClockIcon, Music2Icon, RefreshCwIcon, TimerIcon, Volume2Icon } from "lucide-react";
import { memo, useEffect, useState } from "react";

const LIKED_SONGS_URL = "https://music.youtube.com/playlist?list=LM";
const SYNC_MAX_ITEMS = 1000;

const ReplayGainButton = memo(function ReplayGainButton() {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async () => {
    setIsLoading(true);
    try {
      const ok = await startReplayGainScan();
      if (ok) {
        showSuccessToast("ReplayGain", "Scan started");
      } else {
        showErrorToast("ReplayGain", "Failed to start scan");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Tooltip content="Re-apply ReplayGain tags to all files" offset={14}>
      <Button
        radius="lg"
        variant="flat"
        onPress={handleClick}
        isLoading={isLoading}
        startContent={!isLoading && <Volume2Icon className="h-4 w-4" />}
      >
        ReplayGain
      </Button>
    </Tooltip>
  );
});

function SyncSection({ onSync }: { onSync: () => void }) {
  return (
    <section className="mb-8 flex gap-2">
      <Button
        color="primary"
        radius="lg"
        variant="shadow"
        onPress={onSync}
        startContent={<RefreshCwIcon className="h-4 w-4" />}
      >
        Sync Now
      </Button>
      <ReplayGainButton />
    </section>
  );
}

function NextSyncCard({ status }: { status: SchedulerStatus | null }) {
  const countdown = useScheduleCountdown(
    status?.cron_expression,
    status?.timezone,
  );

  return (
    <SubscriptionCard>
      <SubscriptionCard.Header title="Next sync">
        <SubscriptionCard.Value>
          <span className="font-mono">{countdown}</span>
        </SubscriptionCard.Value>
      </SubscriptionCard.Header>
      <SubscriptionCard.Icon className="text-secondary bg-secondary/10">
        <TimerIcon />
      </SubscriptionCard.Icon>
    </SubscriptionCard>
  );
}

function Dashboard({ jobs, schedulerStatus }: {
  jobs: ReturnType<typeof useJobs>["jobs"];
  schedulerStatus: SchedulerStatus | null;
}) {
  const lastCompleted = jobs.find((j) => j.status === "completed");
  const trackCount = lastCompleted?.content_info?.track_count;
  const lastSyncedAt = lastCompleted?.completed_at;
  const timeAgo = useTimeAgo(lastSyncedAt);

  return (
    <div className="mb-6 grid w-full grid-cols-3 gap-4">
      <SubscriptionCard>
        <SubscriptionCard.Header title="Last synced">
          <SubscriptionCard.Value>
            <span className="font-mono">{timeAgo}</span>
          </SubscriptionCard.Value>
        </SubscriptionCard.Header>
        <SubscriptionCard.Icon className="text-success bg-success/10">
          <ClockIcon />
        </SubscriptionCard.Icon>
      </SubscriptionCard>
      <SubscriptionCard>
        <SubscriptionCard.Header title="Tracks">
          <SubscriptionCard.Value>
            <span className="font-mono">{trackCount ?? "—"}</span>
          </SubscriptionCard.Value>
        </SubscriptionCard.Header>
        <SubscriptionCard.Icon className="text-primary bg-primary/10">
          <Music2Icon />
        </SubscriptionCard.Icon>
      </SubscriptionCard>
      <NextSyncCard status={schedulerStatus} />
    </div>
  );
}

export function JobsPage() {
  const { jobs, isLoading, startJob, cancelJob, deleteJob, retryJob } = useJobs();
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);

  useEffect(() => {
    getStatus().then(setSchedulerStatus);
  }, []);

  const handleSync = () => {
    startJob(LIKED_SONGS_URL, SYNC_MAX_ITEMS);
  };

  const handleDeleteJob = async (jobId: string) => {
    await deleteJob(jobId);
  };

  const reviewJob = jobs.find((j) => j.status === "awaiting_review");

  return (
    <>
      <h1 className="text-foreground mb-6 text-2xl font-bold">Sync</h1>

      <SyncSection onSync={handleSync} />

      <Dashboard jobs={jobs} schedulerStatus={schedulerStatus} />

      <section className="flex flex-col gap-6">
        {reviewJob && <OrphanReview job={reviewJob} />}
        <JobsPanel
          jobs={jobs}
          isLoading={isLoading}
          onCancel={cancelJob}
          onDelete={handleDeleteJob}
          onRetry={retryJob}
        />
        <LogsPanel jobs={jobs} />
      </section>
    </>
  );
}
