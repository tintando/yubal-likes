import {
  Panel,
  PanelContent,
  PanelHeader,
} from "@/components/common/panel";
import { useLikedSongs } from "./use-liked-songs";
import { LikedSongRow } from "./liked-song-row";
import { Button, Input, Spinner } from "@heroui/react";
import { HeartIcon, RefreshCwIcon, SearchIcon } from "lucide-react";

export function LikesPanel() {
  const {
    songs,
    totalCount,
    isLoading,
    error,
    searchQuery,
    setSearchQuery,
    fetchSongs,
    unlike,
    deleteFiles,
    redownload,
  } = useLikedSongs();

  return (
    <Panel>
      <PanelHeader
        leadingIcon={<HeartIcon className="h-4 w-4" />}
        badge={
          totalCount > 0 ? (
            <span className="text-foreground-400 text-xs">
              {songs.length !== totalCount
                ? `${songs.length} / ${totalCount}`
                : totalCount}
            </span>
          ) : undefined
        }
        trailingIcon={
          <Button
            isIconOnly
            size="sm"
            variant="light"
            onPress={fetchSongs}
            isLoading={isLoading}
            aria-label="Refresh"
          >
            <RefreshCwIcon className="h-4 w-4" />
          </Button>
        }
      >
        Liked Songs
      </PanelHeader>

      <div className="px-4 pb-2">
        <Input
          size="sm"
          placeholder="Search by title, artist, or album..."
          value={searchQuery}
          onValueChange={setSearchQuery}
          startContent={
            <SearchIcon className="text-foreground-400 h-4 w-4 shrink-0" />
          }
          isClearable
          onClear={() => setSearchQuery("")}
        />
      </div>

      <PanelContent height="h-[calc(100vh-16rem)]">
        {isLoading && songs.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : error && songs.length === 0 ? (
          <div className="text-foreground-400 flex h-full items-center justify-center text-sm">
            {error}
          </div>
        ) : songs.length === 0 ? (
          <div className="text-foreground-400 flex h-full items-center justify-center text-sm">
            {searchQuery ? "No songs match your search" : "No liked songs found"}
          </div>
        ) : (
          <div className="flex flex-col gap-0.5">
            {songs.map((song) => (
              <LikedSongRow
                key={song.video_id}
                song={song}
                onUnlike={unlike}
                onDelete={deleteFiles}
                onRedownload={redownload}
              />
            ))}
          </div>
        )}
      </PanelContent>
    </Panel>
  );
}
