import type { Job } from "@/api/jobs";
import { EmptyState } from "@/components/common/empty-state";
import { Panel, PanelContent, PanelHeader } from "@/components/common/panel";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { isActive } from "@/lib/job-status";
import { Chip, Spinner } from "@heroui/react";
import { ChevronDownIcon, CloudOffIcon, TerminalIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { LogLine } from "./log-line";
import { useLogs } from "./use-logs";

type Props = {
  jobs?: Job[];
};

export function LogsPanel({ jobs = [] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { lines, isOffline } = useLogs();
  const [isExpanded, setIsExpanded] = useLocalStorage(
    "yubal-logs-expanded",
    false,
  );

  const hasActiveJobs = jobs.some((job) => isActive(job.status));

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [lines]);

  return (
    <Panel className="flex-1 min-h-0">
      <PanelHeader
        className="hover:bg-content2 cursor-pointer select-none"
        onClick={() => setIsExpanded(!isExpanded)}
        leadingIcon={<TerminalIcon size={18} />}
        badge={
          isOffline ? (
            <Chip
              size="sm"
              radius="full"
              color="warning"
              variant="flat"
              startContent={<CloudOffIcon size={16} className="mr-1 ml-1" />}
            >
              offline
            </Chip>
          ) : hasActiveJobs ? (
            <span className="flex items-center">
              <Spinner
                size="sm"
                variant="wave"
                color="primary"
                className="align-middle"
                classNames={{
                  wrapper: "h-full",
                }}
              />
            </span>
          ) : null
        }
        trailingIcon={
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="flex items-center justify-center"
          >
            <ChevronDownIcon size={18} />
          </motion.div>
        }
      >
        logs
      </PanelHeader>
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <PanelContent
              ref={containerRef}
              height="max-h-96"
              className="logs-container space-y-0.5 p-4 font-mono text-xs"
            >
              {lines.length === 0 ? (
                <EmptyState icon={TerminalIcon} title="No activity yet" mono />
              ) : (
                lines.map((line) => (
                  <div key={line.id}>
                    <LogLine entry={line.entry} />
                  </div>
                ))
              )}
            </PanelContent>
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  );
}
