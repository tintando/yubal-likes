import type { Job } from "@/api/jobs";
import { resolveOrphans } from "@/api/jobs";
import type { components } from "@/api/schema";
import { Panel, PanelContent, PanelHeader } from "@/components/common/panel";
import { showErrorToast, showSuccessToast } from "@/lib/toast";
import { Button, Tooltip } from "@heroui/react";
import {
  AlertTriangleIcon,
  CheckIcon,
  ShieldIcon,
  SkipForwardIcon,
  Trash2Icon,
} from "lucide-react";
import { useMemo, useState } from "react";

type OrphanFile = components["schemas"]["OrphanFile"];
type Action = "delete" | "keep" | "never_delete";

/** A group of orphan files sharing the same stem (e.g. track.opus + track.lrc) */
type OrphanGroup = {
  /** Path without extension, used as group key */
  stem: string;
  /** Display name without extension */
  name: string;
  /** Parent folder path */
  folder: string;
  /** Extensions in the group (e.g. [".opus", ".lrc"]) */
  extensions: string[];
  /** Individual file paths */
  paths: string[];
  /** Combined size of all files */
  totalSize: number;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function splitPath(path: string): { folder: string; stem: string; ext: string } {
  const lastSlash = path.lastIndexOf("/");
  const folder = lastSlash >= 0 ? path.slice(0, lastSlash) : "";
  const filename = lastSlash >= 0 ? path.slice(lastSlash + 1) : path;
  const dotIdx = filename.lastIndexOf(".");
  const stem = dotIdx > 0 ? filename.slice(0, dotIdx) : filename;
  const ext = dotIdx > 0 ? filename.slice(dotIdx) : "";
  return { folder, stem, ext };
}

function groupOrphans(orphans: OrphanFile[]): OrphanGroup[] {
  const map = new Map<string, OrphanGroup>();

  for (const o of orphans) {
    const { folder, stem, ext } = splitPath(o.path);
    const key = folder ? `${folder}/${stem}` : stem;

    let group = map.get(key);
    if (!group) {
      group = { stem: key, name: stem, folder, extensions: [], paths: [], totalSize: 0 };
      map.set(key, group);
    }
    group.extensions.push(ext);
    group.paths.push(o.path);
    group.totalSize += o.size;
  }

  return Array.from(map.values());
}

function OrphanRow({
  group,
  action,
  onAction,
}: {
  group: OrphanGroup;
  action: Action;
  onAction: (action: Action) => void;
}) {
  const extLabel = group.extensions.sort().join(" + ");

  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5">
          <p className="text-foreground text-small truncate font-mono">
            {group.name}
          </p>
          <span className="text-foreground-400 text-tiny shrink-0 font-mono">
            {extLabel}
          </span>
        </div>
        {group.folder && (
          <p className="text-foreground-400 text-tiny truncate">{group.folder}</p>
        )}
      </div>
      <span className="text-foreground-500 text-tiny shrink-0 font-mono">
        {formatSize(group.totalSize)}
      </span>
      <div className="flex shrink-0 items-center gap-1">
        <Tooltip content="Delete" closeDelay={0}>
          <Button
            variant={action === "delete" ? "flat" : "light"}
            size="sm"
            isIconOnly
            color={action === "delete" ? "danger" : "default"}
            className="h-7 w-7"
            onPress={() => onAction("delete")}
          >
            <Trash2Icon className="h-3.5 w-3.5" />
          </Button>
        </Tooltip>
        <Tooltip content="Keep for now" closeDelay={0}>
          <Button
            variant={action === "keep" ? "flat" : "light"}
            size="sm"
            isIconOnly
            color={action === "keep" ? "primary" : "default"}
            className="h-7 w-7"
            onPress={() => onAction("keep")}
          >
            <SkipForwardIcon className="h-3.5 w-3.5" />
          </Button>
        </Tooltip>
        <Tooltip content="Never delete" closeDelay={0}>
          <Button
            variant={action === "never_delete" ? "flat" : "light"}
            size="sm"
            isIconOnly
            color={action === "never_delete" ? "success" : "default"}
            className="h-7 w-7"
            onPress={() => onAction("never_delete")}
          >
            <ShieldIcon className="h-3.5 w-3.5" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

export function OrphanReview({ job }: { job: Job }) {
  const orphans = job.pending_orphans ?? [];
  const groups = useMemo(() => groupOrphans(orphans), [orphans]);

  // Decisions keyed by group stem
  const [decisions, setDecisions] = useState<Record<string, Action>>(() => {
    const initial: Record<string, Action> = {};
    for (const g of groups) {
      initial[g.stem] = "delete";
    }
    return initial;
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setAction = (stem: string, action: Action) => {
    setDecisions((prev) => ({ ...prev, [stem]: action }));
  };

  const setAllKeep = () => {
    setDecisions((prev) => {
      const next = { ...prev };
      for (const key of Object.keys(next)) {
        next[key] = "keep";
      }
      return next;
    });
  };

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      // Expand group decisions back to individual file paths
      const items: { path: string; action: Action }[] = [];
      for (const group of groups) {
        const action = decisions[group.stem] ?? "delete";
        for (const path of group.paths) {
          items.push({ path, action });
        }
      }
      const ok = await resolveOrphans(job.id, items);
      if (ok) {
        showSuccessToast("Cleanup", "Orphan review complete");
      } else {
        showErrorToast("Cleanup", "Failed to resolve orphans");
      }
    } catch {
      showErrorToast("Cleanup", "Failed to resolve orphans");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (groups.length === 0) return null;

  const deleteCount = groups.filter(
    (g) => (decisions[g.stem] ?? "delete") === "delete",
  ).length;

  return (
    <Panel>
      <PanelHeader leadingIcon={<AlertTriangleIcon size={18} className="text-warning" />}>
        Orphan review
      </PanelHeader>
      <PanelContent height="h-80" className="space-y-0">
        <div className="divide-divider flex flex-col divide-y overflow-y-auto">
          {groups.map((group) => (
            <OrphanRow
              key={group.stem}
              group={group}
              action={decisions[group.stem] ?? "delete"}
              onAction={(action) => setAction(group.stem, action)}
            />
          ))}
        </div>
      </PanelContent>
      <div className="flex items-center justify-between border-t px-4 py-3">
        <Button variant="flat" size="sm" radius="lg" onPress={setAllKeep}>
          Keep all
        </Button>
        <Button
          color="primary"
          size="sm"
          radius="lg"
          isLoading={isSubmitting}
          startContent={!isSubmitting && <CheckIcon className="h-4 w-4" />}
          onPress={handleConfirm}
        >
          Confirm{deleteCount > 0 ? ` (delete ${deleteCount})` : ""}
        </Button>
      </div>
    </Panel>
  );
}
