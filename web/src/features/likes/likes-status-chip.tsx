import type { LikedSong } from "@/api/likes";
import { Chip } from "@heroui/react";
import { tv } from "tailwind-variants";

const statusChip = tv({
  base: "font-mono",
  variants: {
    status: {
      changed: "bg-warning/15 text-warning-600 dark:text-warning-400",
      new: "bg-primary/15 text-primary",
    },
  },
});

export function LikesStatusChip({ status }: { status: LikedSong["status"] }) {
  if (status === "synced") return null;

  return (
    <Chip
      size="sm"
      variant="flat"
      classNames={{
        base: statusChip({ status }),
      }}
    >
      {status}
    </Chip>
  );
}
