import { startReplayGainScan } from "@/api/replaygain";
import { UrlInput } from "@/components/common/url-input";
import { LogsPanel } from "@/features/logs/logs-panel";
import { JobsPanel } from "@/features/jobs/jobs-panel";
import { useJobs } from "@/features/jobs/jobs-context";
import { isValidUrl } from "@/lib/url";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { Button, Input, Tooltip } from "@heroui/react";
import { DownloadIcon, HashIcon, Volume2Icon } from "lucide-react";
import { memo, useState } from "react";

const DEFAULT_MAX_ITEMS = 100;

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

interface DownloadFormProps {
  onDownload: (url: string, maxItems: number) => Promise<void>;
}

const DownloadForm = memo(function DownloadForm({
  onDownload,
}: DownloadFormProps) {
  const [url, setUrl] = useState("");
  const [maxItems, setMaxItems] = useState(DEFAULT_MAX_ITEMS);

  const canDownload = isValidUrl(url);

  const handleDownload = async () => {
    if (canDownload) {
      await onDownload(url, maxItems);
      setUrl("");
    }
  };

  return (
    <section className="mb-8 flex gap-2">
      <div className="flex-1">
        <UrlInput value={url} onChange={setUrl} />
      </div>
      <Tooltip content="Max number of tracks to download" offset={14}>
        <Input
          type="number"
          value={String(maxItems)}
          onChange={(e) => {
            const value = parseInt(e.target.value, 10);
            if (!Number.isNaN(value) && value >= 1) setMaxItems(value);
          }}
          min={1}
          max={10000}
          radius="lg"
          placeholder="Max"
          startContent={<HashIcon className="text-foreground-400 h-4 w-4" />}
          classNames={{
            base: "w-24",
            input: "font-mono",
          }}
        />
      </Tooltip>
      <Button
        color="primary"
        radius="lg"
        variant={canDownload ? "shadow" : "solid"}
        className="shadow-primary-100/50"
        onPress={handleDownload}
        isDisabled={!canDownload}
        startContent={<DownloadIcon className="h-4 w-4" />}
      >
        Download
      </Button>
      <ReplayGainButton />
    </section>
  );
});

export function JobsPage() {
  const { jobs, isLoading, startJob, cancelJob, deleteJob } = useJobs();

  const handleDeleteJob = async (jobId: string) => {
    await deleteJob(jobId);
  };

  return (
    <>
      {/* Page Title */}
      <h1 className="text-foreground mb-6 text-2xl font-bold">Downloads</h1>

      {/* URL Input Section */}
      <DownloadForm onDownload={startJob} />

      {/* Downloads Panels */}
      <section className="flex flex-col gap-6">
        <JobsPanel
          jobs={jobs}
          isLoading={isLoading}
          onCancel={cancelJob}
          onDelete={handleDeleteJob}
        />
        <LogsPanel jobs={jobs} />
      </section>
    </>
  );
}
