import type { LikedSong } from "@/api/likes";
import {
  Button,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Tooltip,
} from "@heroui/react";
import { CheckIcon, HeartOffIcon, RefreshCwIcon, Trash2Icon } from "lucide-react";
import { memo, useState } from "react";
import { LikesStatusChip } from "./likes-status-chip";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  song: LikedSong;
  onUnlike: (videoId: string) => Promise<void>;
  onDelete: (videoId: string) => Promise<void>;
  onRedownload: (videoId: string) => Promise<void>;
  onDismiss: (videoId: string) => Promise<void>;
}

export const LikedSongRow = memo(function LikedSongRow({
  song,
  onUnlike,
  onDelete,
  onRedownload,
  onDismiss,
}: Props) {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleAction = async (
    action: string,
    fn: (id: string) => Promise<void>,
  ) => {
    setLoadingAction(action);
    try {
      await fn(song.video_id);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-default-100">
      {/* Thumbnail */}
      {song.thumbnail_url ? (
        <img
          src={song.thumbnail_url}
          alt=""
          className="h-10 w-10 shrink-0 rounded object-cover"
          loading="lazy"
          onError={(e) => {
            e.currentTarget.style.display = "none";
            e.currentTarget.nextElementSibling?.classList.remove("hidden");
          }}
        />
      ) : null}
      <div
        className={`bg-default-200 h-10 w-10 shrink-0 rounded${song.thumbnail_url ? " hidden" : ""}`}
      />

      {/* Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="text-foreground truncate text-sm font-medium">
            {song.title}
          </p>
          {song.status === "changed" && song.synced_title ? (
            <Tooltip content={`was: ${song.synced_title}`} closeDelay={0}>
              <span className="shrink-0">
                <LikesStatusChip status={song.status} />
              </span>
            </Tooltip>
          ) : (
            <LikesStatusChip status={song.status} />
          )}
        </div>
        <p className="text-foreground-500 truncate text-xs">
          {song.artists.join(", ")}
          {song.album && ` · ${song.album}`}
        </p>
      </div>

      {/* Duration */}
      <span className="text-foreground-400 shrink-0 text-xs tabular-nums">
        {formatDuration(song.duration_seconds)}
      </span>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-1">
        {song.status === "changed" && (
          <Tooltip content="Accept change (keep local files)">
            <Button
              isIconOnly
              size="sm"
              variant="light"
              isLoading={loadingAction === "dismiss"}
              onPress={() => handleAction("dismiss", onDismiss)}
              aria-label="Dismiss change"
            >
              <CheckIcon className="h-4 w-4" />
            </Button>
          </Tooltip>
        )}
        <Popover placement="top">
          <PopoverTrigger>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              isLoading={loadingAction === "unlike"}
              aria-label="Unlike"
            >
              <HeartOffIcon className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent>
            <div className="flex flex-col gap-2 p-2">
              <p className="text-sm">Remove from YTM Liked Songs?</p>
              <Button
                size="sm"
                color="danger"
                onPress={() => handleAction("unlike", onUnlike)}
              >
                Remove
              </Button>
            </div>
          </PopoverContent>
        </Popover>

        <Popover placement="top">
          <PopoverTrigger>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              isLoading={loadingAction === "delete"}
              aria-label="Delete files"
            >
              <Trash2Icon className="h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent>
            <div className="flex flex-col gap-2 p-2">
              <p className="text-sm">Delete local and Drive files?</p>
              <Button
                size="sm"
                color="danger"
                onPress={() => handleAction("delete", onDelete)}
              >
                Delete
              </Button>
            </div>
          </PopoverContent>
        </Popover>

        <Tooltip content="Redownload">
          <Button
            isIconOnly
            size="sm"
            variant="light"
            isLoading={loadingAction === "redownload"}
            onPress={() => handleAction("redownload", onRedownload)}
            aria-label="Redownload"
          >
            <RefreshCwIcon className="h-4 w-4" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
});
